"""CLI 内部工具函数与共享单例

不应被外部直接 import；命令文件通过 `from doc_knowledge.cli._helpers import ...` 使用。
"""

import re
import shutil
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from doc_knowledge.config import load_config
from doc_knowledge.converters import convert_file, get_supported_extensions
from doc_knowledge.extractors.deduplicator import Deduplicator
from doc_knowledge.extractors.scorer import ValueScorer
from doc_knowledge.extractors.tagger import Tagger
from doc_knowledge.extractors.merger import VersionMerger
from doc_knowledge.extractors.simhash_dedup import SimHashDeduplicator
from doc_knowledge.ocr import create_ocr_service
from doc_knowledge.utils import make_frontmatter


console = Console()


def _setup_ocr(ocr_mode, ocr_api_url="", ocr_api_key="", ocr_model=""):
    """根据 CLI 参数 + 配置文件创建 OCR 服务"""
    cfg = load_config()

    if ocr_mode:
        cfg.ocr.enabled = True
        cfg.ocr.mode = ocr_mode
    if ocr_api_url:
        cfg.ocr.cloud.api_url = ocr_api_url
    if ocr_api_key:
        cfg.ocr.cloud.api_key = ocr_api_key
    if ocr_model:
        cfg.ocr.cloud.model = ocr_model

    if not cfg.ocr.enabled:
        return None

    try:
        return create_ocr_service(cfg)
    except NotImplementedError as e:
        if cfg.ocr.mode == "local" and cfg.ocr.local.engine == "paddleocr":
            console.print(
                f"[yellow]PaddleOCR 不可用（{e}），回退到 Tesseract[/yellow]"
            )
            cfg.ocr.local.engine = "tesseract"
            try:
                return create_ocr_service(cfg)
            except Exception:
                pass
        console.print(f"[yellow]警告：{e}[/yellow]")
        return None


def _run_convert(source_dir, output_dir, formats=None, recursive=True, verbose=False,
                 ocr_service=None, dry_run=False):
    """convert 核心逻辑（CLI 和 pipeline 共用），返回 stats dict"""
    source_dir = source_dir.resolve()
    output_dir = output_dir.resolve()

    all_files = list(source_dir.rglob("*") if recursive else source_dir.iterdir())
    all_files = [f for f in all_files if f.is_file()]

    stats = {"converted": 0, "copied": 0, "skipped": 0, "errors": 0, "images": 0}

    if not all_files:
        console.print("[yellow]未找到任何文件[/yellow]")
        return stats

    supported = set(get_supported_extensions())
    format_filter = set(f".{f.lower().lstrip('.')}" for f in (formats or [])) if formats else None

    to_convert, to_copy, to_skip = [], [], []
    for f in sorted(all_files):
        ext = f.suffix.lower()
        if format_filter and ext not in format_filter:
            continue
        if ext in supported:
            to_convert.append(f)
        elif ext in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg"}:
            to_copy.append(f)
        else:
            to_skip.append(f)

    if verbose or dry_run:
        console.print(f"[dim]可转换: {len(to_convert)}, 图片: {len(to_copy)}, 其他: {len(to_skip)}[/dim]")

    if dry_run:
        stats["to_convert"] = to_convert
        stats["to_copy"] = to_copy
        stats["to_skip"] = to_skip
        return stats

    output_dir.mkdir(parents=True, exist_ok=True)

    with Progress(
        SpinnerColumn(), BarColumn(), TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("转换中...", total=len(to_convert))
        for source_file in to_convert:
            rel = source_file.relative_to(source_dir)
            progress.update(task, description=f"转换: {rel}")
            try:
                result = convert_file(
                    source_file, output_dir=output_dir,
                    ocr_service=ocr_service,
                    verbose=verbose,
                )
                if isinstance(result, tuple):
                    markdown, images, image_map = result
                else:
                    markdown = result
                    images = 0
                    image_map = {}

                if image_map:
                    for old_name, new_path in image_map.items():
                        markdown = markdown.replace(f"]({old_name})", f"]({new_path})")

                frontmatter = make_frontmatter(
                    title=source_file.stem, source_path=source_file.resolve(),
                    source_relative=str(rel), original_format=source_file.suffix.lstrip("."),
                )
                if images > 0:
                    frontmatter += f"images_extracted: {images}\n"
                output_file = output_dir / rel.parent / f"{source_file.name}.md"
                output_file.parent.mkdir(parents=True, exist_ok=True)
                output_file.write_text(frontmatter + markdown, encoding="utf-8")
                stats["converted"] += 1
                stats["images"] += images
                if verbose and images > 0:
                    console.print(f"  [green]+ {rel}: {images} images extracted[/green]")
            except Exception as e:
                stats["errors"] += 1
                if verbose:
                    err_msg = str(e)[:200].encode("ascii", errors="replace").decode("ascii")
                    console.print(f"  [red]X {rel}: {err_msg}[/red]")
            progress.advance(task)

    for img in to_copy:
        rel = img.relative_to(source_dir)
        dest = output_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(img, dest)
        stats["copied"] += 1

    for other in to_skip:
        rel = other.relative_to(source_dir)
        dest = output_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(other, dest)
        wrapper = dest.parent / f"{other.name}.md"
        wrapper.write_text(make_frontmatter(
            title=other.name, source_path=other.resolve(),
            source_relative=str(rel), original_format=other.suffix.lstrip("."),
            conversion_status="skipped",
        ), encoding="utf-8")
        stats["skipped"] += 1

    console.print(f"[dim]转换: {stats['converted']}, 图片: {stats['images']}, "
                  f"复制: {stats['copied']}, 跳过: {stats['skipped']}, 错误: {stats['errors']}[/dim]")

    return stats


def _run_extract(mirror_dir, output_dir, threshold=0.85, min_score=30,
                 keep_deprecated=False, simhash=False, merge=False,
                 incremental=False, previous_output=None, verbose=False):
    """extract 的内部逻辑（供 pipeline 调用）"""
    mirror_dir = mirror_dir.resolve()
    output_dir = output_dir.resolve()

    # 增量更新：检查哪些文件是新的
    if incremental and output_dir.exists():
        console.print("[dim]增量模式：仅处理变更文件...[/dim]")
        # 获取已存在的文件
        existing = {f.name: f for f in output_dir.rglob("*.md")}

    md_files = sorted(mirror_dir.rglob("*.md"))
    if not md_files:
        console.print("[yellow]未找到 Markdown 文件[/yellow]")
        return

    documents = []
    scorer = ValueScorer(min_score=min_score)
    tagger = Tagger()

    for md_file in md_files:
        # 增量模式：跳过未变更的文件
        if incremental and output_dir.exists():
            rel = md_file.relative_to(mirror_dir)
            existing_file = output_dir / rel
            if existing_file.exists():
                try:
                    if md_file.stat().st_mtime <= existing_file.stat().st_mtime:
                        continue  # 未变更，跳过
                except OSError:
                    pass

        content = md_file.read_text(encoding="utf-8")
        score_result = scorer.score(content, md_file)
        tags = tagger.tag(content, title=md_file.stem)
        documents.append({
            "path": md_file, "content": content,
            "score": score_result["total"], "score_detail": score_result, "tags": tags,
        })

    # 去重
    if simhash:
        dedup = SimHashDeduplicator(threshold=int(threshold * 64))
    else:
        dedup = Deduplicator(threshold=threshold)
    kept, duplicates = dedup.deduplicate(documents)

    # 版本合并
    if merge and kept:
        merger = VersionMerger()
        kept, merged_docs = merger.merge(kept)
        duplicates.extend(merged_docs)

    output_dir.mkdir(parents=True, exist_ok=True)
    if keep_deprecated:
        (output_dir / "deprecated").mkdir(exist_ok=True)

    stats = {"kept": 0, "deduped": 0, "low_score": 0}

    for doc in kept:
        if doc["score"] < min_score:
            stats["low_score"] += 1
            continue
        content = _add_extract_frontmatter(doc["content"], doc)
        rel = doc["path"].relative_to(mirror_dir)
        content = _fixup_image_refs(content, rel, mirror_dir.name)
        dest = output_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        stats["kept"] += 1

    console.print(f"[dim]保留: {stats['kept']}, 去重: {len(duplicates)}, "
                  f"低分: {stats['low_score']}, 合并: {len([d for d in duplicates if 'merged_into' in d])}[/dim]")


def _fixup_image_refs(markdown: str, rel_path: Path, mirror_name: str) -> str:
    """将 Markdown 中的图片引用改为指向镜像目录 B

    从 C（或最终输出）通过相对路径指回 B 中的图片文件。
    """
    depth = len(rel_path.parent.parts) if str(rel_path.parent) != '.' else 0
    prefix = '../' * (depth + 1) + mirror_name + '/'
    rel_dir = str(rel_path.parent).replace('\\', '/')
    if rel_dir and rel_dir != '.':
        prefix += rel_dir + '/'

    def rewrite(match):
        ref = match.group(2)
        # 已修复的或外部链接不重复处理
        if ref.startswith(('http://', 'https://', '../')):
            return match.group(0)
        return f"![{match.group(1)}]({prefix}{ref})"

    return re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', rewrite, markdown)


def _add_extract_frontmatter(content: str, doc: dict) -> str:
    """在 frontmatter 中添加提取元数据（评分、标签等）"""
    fm_match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)

    score_data = doc["score_detail"]
    tags_str = ", ".join(f"\"{t}\"" for t in doc["tags"]) if doc["tags"] else "[]"

    extract_meta = (
        f"\ndk_score: {doc['score']}\n"
        f"dk_score_detail:\n"
        f"  length: {score_data['length']}\n"
        f"  structure: {score_data['structure']}\n"
        f"  freshness: {score_data['freshness']}\n"
        f"  keywords: {score_data['keywords']}\n"
        f"  uniqueness: {score_data['uniqueness']}\n"
        f"dk_tags: [{tags_str}]\n"
    )

    if fm_match:
        fm_content = fm_match.group(1)
        rest = content[fm_match.end():]
        # 插入到 frontmatter 末尾
        new_fm = fm_content + extract_meta
        return f"---\n{new_fm}---\n\n{rest}"
    else:
        header = f"---\n{extract_meta}---\n\n"
        return header + content


def _run_memomind_post_processing(db_path, workspace, run_dedup, run_consolidate):
    """执行 MemoMind 后处理（延迟导入）

    Args:
        db_path: Path 对象，MemoMind SQLite 数据库路径
        workspace: 工作区名称
        run_dedup: 是否运行去重扫描
        run_consolidate: 是否运行知识整理建议
    """
    try:
        from doc_knowledge.exporters.memomind_post import (
            run_dedup_report,
            run_consolidation_report,
        )
    except ImportError as e:
        console.print(f"[yellow]后处理跳过：{e}[/yellow]")
        return

    db_str = str(db_path)
    if run_dedup:
        try:
            run_dedup_report(db_str, workspace_name=workspace)
        except Exception as e:
            console.print(f"[yellow]去重扫描失败: {e}[/yellow]")

    if run_consolidate:
        try:
            run_consolidation_report(db_str, workspace_name=workspace)
        except Exception as e:
            console.print(f"[yellow]知识整理失败: {e}[/yellow]")
