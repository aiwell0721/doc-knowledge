"""
Doc-Knowledge CLI 入口

4 个命令覆盖全链路：convert / extract / export / pipeline
"""

import json
import shutil
import tempfile
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from doc_knowledge import __version__
from doc_knowledge.converters import convert_file, get_supported_extensions
from doc_knowledge.extractors.deduplicator import Deduplicator
from doc_knowledge.extractors.scorer import ValueScorer
from doc_knowledge.extractors.tagger import Tagger
from doc_knowledge.exporters.obsidian import ObsidianExporter, MarkdownExporter
from doc_knowledge.exporters.memomind import MemoMindExporter, MemoMindMCPExporter
from doc_knowledge.extractors.merger import VersionMerger
from doc_knowledge.extractors.simhash_dedup import SimHashDeduplicator
from doc_knowledge.utils import make_frontmatter
from doc_knowledge.vision import LLMVisionService


console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="doc-knowledge")
def main():
    """Doc-Knowledge: 文档知识提取工具"""
    pass


# ──────────────────────────────────────────────
# convert 命令 (A → B)
# ──────────────────────────────────────────────

@main.command()
@click.argument("source_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("-o", "--output", "output_dir", type=click.Path(path_type=Path),
              help="输出目录（目录 B），默认为 <source_dir>_mirror")
@click.option("--format", "formats", multiple=True,
              help="仅转换指定格式，如 --format pdf --format docx")
@click.option("--recursive/--no-recursive", default=True,
              help="是否递归子目录")
@click.option("--overwrite", is_flag=True,
              help="覆盖已存在的文件")
@click.option("--dry-run", is_flag=True,
              help="仅显示将要转换的文件，不实际转换")
@click.option("--vision", is_flag=True,
              help="启用大模型图片识别（需要配置 API）")
@click.option("--api-url", "vision_api_url", default="",
              help="大模型 API 地址（OpenAI 兼容）")
@click.option("--api-key", "vision_api_key", default="",
              help="大模型 API Key")
@click.option("--model", "vision_model", default="qwen-vl-plus",
              help="大模型名称")
@click.option("-v", "--verbose", is_flag=True,
              help="详细输出")
def convert(source_dir, output_dir, formats, recursive, overwrite, dry_run,
            vision, vision_api_url, vision_api_key, vision_model, verbose):
    """将文档转换为 Markdown 镜像（A → B）"""
    source_dir = source_dir.resolve()
    if output_dir is None:
        output_dir = source_dir.parent / f"{source_dir.name}_mirror"
    output_dir = output_dir.resolve()

    console.print(f"[bold green]Doc-Knowledge v{__version__} — convert[/bold green]")
    console.print(f"源目录: [cyan]{source_dir}[/cyan]")
    console.print(f"输出目录: [cyan]{output_dir}[/cyan]")

    # 初始化视觉识别服务
    vision_service = None
    if vision and vision_api_key:
        api_url = vision_api_url or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        vision_service = LLMVisionService(
            api_url=api_url,
            api_key=vision_api_key,
            model=vision_model,
        )
        console.print(f"[dim]图片识别: {vision_model} ({api_url})[/dim]")
    elif vision and not vision_api_key:
        console.print("[yellow]警告：--vision 已启用但未提供 --api-key，跳过图片识别[/yellow]")
    all_files = list(source_dir.rglob("*") if recursive else source_dir.iterdir())
    all_files = [f for f in all_files if f.is_file()]

    if not all_files:
        console.print("[yellow]未找到任何文件[/yellow]")
        return

    # 过滤可转换的文件
    supported = set(get_supported_extensions())
    format_filter = set(f".{f.lower().lstrip('.')}" for f in formats) if formats else None

    to_convert = []
    to_copy = []  # 图片等
    to_skip = []  # 不支持的格式

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

    if dry_run or verbose:
        console.print(f"[dim]可转换: {len(to_convert)}, 图片: {len(to_copy)}, 其他: {len(to_skip)}[/dim]")
        if dry_run:
            for f in to_convert:
                console.print(f"  [MD] {f.relative_to(source_dir)}")
            for f in to_copy:
                console.print(f"  [CP] {f.relative_to(source_dir)}")
            return

    # 执行转换
    output_dir.mkdir(parents=True, exist_ok=True)
    stats = {"converted": 0, "copied": 0, "skipped": 0, "errors": 0, "images": 0}

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
                    source_file, 
                    output_dir=output_dir, 
                    vision_service=vision_service,
                    verbose=verbose,
                )
                if isinstance(result, tuple):
                    markdown, images, image_map = result
                else:
                    markdown = result
                    images = 0
                    image_map = {}
                
                # Update image references in markdown
                if image_map:
                    for old_name, new_path in image_map.items():
                        markdown = markdown.replace(f"]({old_name})", f"]({new_path})")
                
                frontmatter = make_frontmatter(
                    title=source_file.stem,
                    source_path=source_file.resolve(),
                    source_relative=str(rel),
                    original_format=source_file.suffix.lstrip("."),
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

    # 复制图片
    for img in to_copy:
        rel = img.relative_to(source_dir)
        dest = output_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(img, dest)
        stats["copied"] += 1

    # 其他文件：复制 + 元数据包装
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

    console.print()
    console.print(f"[bold green]完成！转换 {stats['converted']}, 图片 {stats['images']}, "
                  f"复制 {stats['copied']}, 跳过 {stats['skipped']}, 错误 {stats['errors']}[/bold green]")


# ──────────────────────────────────────────────
# extract 命令 (B → C)
# ──────────────────────────────────────────────

@main.command()
@click.argument("mirror_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("-o", "--output", "output_dir", type=click.Path(path_type=Path),
              help="输出目录（目录 C），默认为 <mirror_dir>_extracted")
@click.option("--threshold", default=0.85, show_default=True,
              type=float, help="去重相似度阈值 (0.0-1.0)")
@click.option("--min-score", default=30, show_default=True,
              type=int, help="最低价值评分 (0-100)")
@click.option("--simhash", is_flag=True,
              help="使用 SimHash 去重（适合 10K+ 文件）")
@click.option("--merge", is_flag=True,
              help="启用版本合并（将同一文档的多版本合并为最优版）")
@click.option("--keep-deprecated", is_flag=True,
              help="保留去重的旧版本到 deprecated/ 目录")
@click.option("--dry-run", is_flag=True,
              help="仅显示提取计划")
@click.option("-v", "--verbose", is_flag=True,
              help="详细输出")
def extract(mirror_dir, output_dir, threshold, min_score, simhash, merge,
            keep_deprecated, dry_run, verbose):
    """从 Markdown 镜像提取知识（B → C）"""
    mirror_dir = mirror_dir.resolve()
    if output_dir is None:
        output_dir = mirror_dir.parent / f"{mirror_dir.name}_extracted"
    output_dir = output_dir.resolve()

    console.print(f"[bold green]Doc-Knowledge v{__version__} — extract[/bold green]")
    console.print(f"镜像目录: [cyan]{mirror_dir}[/cyan]")
    console.print(f"输出目录: [cyan]{output_dir}[/cyan]")

    # 收集所有 Markdown 文件
    md_files = sorted(mirror_dir.rglob("*.md"))
    if not md_files:
        console.print("[yellow]未找到 Markdown 文件[/yellow]")
        return

    console.print(f"找到 [cyan]{len(md_files)}[/cyan] 个 Markdown 文件")

    # 读取内容 + 评分
    documents = []
    scorer = ValueScorer(min_score=min_score)
    tagger = Tagger()

    for md_file in md_files:
        content = md_file.read_text(encoding="utf-8")
        score_result = scorer.score(content, md_file)
        tags = tagger.tag(content, title=md_file.stem)

        documents.append({
            "path": md_file,
            "content": content,
            "score": score_result["total"],
            "score_detail": score_result,
            "tags": tags,
        })

    console.print(f"评分完成 — 通过: {sum(1 for d in documents if d['score'] >= min_score)} / "
                  f"淘汰: {sum(1 for d in documents if d['score'] < min_score)}")

    # 去重
    if simhash:
        console.print("[dim]使用 SimHash 去重...[/dim]")
        dedup = SimHashDeduplicator(threshold=int(threshold * 64))
    else:
        dedup = Deduplicator(threshold=threshold)
    kept, duplicates = dedup.deduplicate(documents)

    console.print(f"去重完成 — 保留: {len(kept)}, 重复: {len(duplicates)}")

    # 版本合并
    if merge and kept:
        console.print("[dim]版本合并中...[/dim]")
        merger = VersionMerger()
        kept, merged_docs = merger.merge(kept)
        console.print(f"合并完成 — 保留: {len(kept)}, 合并: {len(merged_docs)}")
        duplicates.extend(merged_docs)

    if dry_run:
        console.print("\n[bold]Dry Run — 计划:[/bold]")
        for d in kept:
            console.print(f"  [green]保留[/green] {d['path'].relative_to(mirror_dir)} "
                          f"(score={d['score']}, tags={d['tags']})")
        for d in duplicates:
            console.print(f"  [yellow]去重[/yellow] {d['path'].relative_to(mirror_dir)} "
                          f"→ similar to {d['similar_to'].name}")
        return

    # 写入输出
    output_dir.mkdir(parents=True, exist_ok=True)
    if keep_deprecated:
        deprecated_dir = output_dir / "deprecated"
        deprecated_dir.mkdir(exist_ok=True)

    stats = {"kept": 0, "deduped": 0, "low_score": 0, "errors": 0}

    for doc in kept:
        if doc["score"] < min_score:
            stats["low_score"] += 1
            if verbose:
                console.print(f"  [yellow]低分跳过[/yellow] {doc['path'].name} (score={doc['score']})")
            continue

        try:
            content = _add_extract_frontmatter(doc["content"], doc)
            rel = doc["path"].relative_to(mirror_dir)
            dest = output_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            stats["kept"] += 1
        except Exception as e:
            stats["errors"] += 1
            if verbose:
                err_msg = str(e)[:200].encode("ascii", errors="replace").decode("ascii")
                console.print(f"  [red]X {doc['path'].name}: {err_msg}[/red]")

    # 处理重复项
    for doc in duplicates:
        stats["deduped"] += 1
        if keep_deprecated:
            try:
                rel = doc["path"].relative_to(mirror_dir)
                dest = deprecated_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                content = _add_extract_frontmatter(doc["content"], doc)
                dest.write_text(content, encoding="utf-8")
            except Exception:
                pass

    console.print()
    console.print(f"[bold green]提取完成！保留 {stats['kept']}, 去重 {stats['deduped']}, "
                  f"低分 {stats['low_score']}, 错误 {stats['errors']}[/bold green]")


# ──────────────────────────────────────────────
# export 命令 (C → 目标)
# ──────────────────────────────────────────────

@main.command()
@click.argument("knowledge_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("-t", "--target", "target_type",
              type=click.Choice(["obsidian", "markdown", "memomind"]),
              default="markdown", show_default=True,
              help="导出目标")
@click.option("--vault", "vault_path", type=click.Path(path_type=Path),
              help="Obsidian Vault 路径 (target=obsidian 时必填)")
@click.option("-o", "--output", "output_dir", type=click.Path(path_type=Path),
              help="输出目录 (target=markdown 时)")
@click.option("--api-url", "api_url", default="",
              help="MemoMind API 地址 (target=memomind 时)")
@click.option("--api-key", "api_key", default="",
              help="MemoMind API Key (可选)")
@click.option("--workspace", "workspace", default="default",
              help="MemoMind 工作区名称")
@click.option("--db", "db_path", type=click.Path(path_type=Path),
              help="MemoMind SQLite 数据库路径 (MCP 本地模式)")
def export_cmd(knowledge_dir, target_type, vault_path, output_dir, api_url, api_key, workspace, db_path):
    """导出知识文档到目标系统（C → 目标）"""
    knowledge_dir = knowledge_dir.resolve()

    console.print(f"[bold green]Doc-Knowledge v{__version__} — export[/bold green]")
    console.print(f"知识目录: [cyan]{knowledge_dir}[/cyan]")
    console.print(f"目标: [cyan]{target_type}[/cyan]")

    if target_type == "obsidian":
        if not vault_path:
            console.print("[red]错误：--vault 是必填项（Obsidian Vault 路径）[/red]")
            raise click.Exit(1)
        exporter = ObsidianExporter(vault_path)
        stats = exporter.export(knowledge_dir)
    elif target_type == "markdown":
        if not output_dir:
            output_dir = knowledge_dir.parent / "exported"
        exporter = MarkdownExporter(output_dir)
        stats = exporter.export(knowledge_dir)
    elif target_type == "memomind":
        if db_path:
            # MCP 本地模式（直接写 SQLite）
            exporter = MemoMindMCPExporter(db_path, workspace=workspace)
        elif api_url:
            exporter = MemoMindExporter(api_url, api_key=api_key, workspace=workspace)
        else:
            console.print("[red]错误：--api-url 或 --db 是必填项（MemoMind 导出）[/red]")
            raise click.Exit(1)
        try:
            stats = exporter.export(knowledge_dir)
        except ConnectionError as e:
            console.print(f"[red]{e}[/red]")
            raise click.Exit(1)
    else:
        console.print(f"[red]未知目标: {target_type}[/red]")
        raise click.Exit(1)

    console.print(f"[bold green]导出完成！成功 {stats['exported']}, 错误 {stats['errors']}[/bold green]")
    if stats.get("error_details"):
        for detail in stats["error_details"]:
            console.print(f"  [red]X {detail}[/red]")


# ──────────────────────────────────────────────
# pipeline 命令 (A → B → C → 导出)
# ──────────────────────────────────────────────

@main.command()
@click.argument("source_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("-o", "--output", "final_output", type=click.Path(path_type=Path),
              help="最终输出目录")
@click.option("-t", "--target", "target_type",
              type=click.Choice(["obsidian", "markdown", "memomind"]),
              default="markdown", show_default=True,
              help="导出目标")
@click.option("--vault", "vault_path", type=click.Path(path_type=Path),
              help="Obsidian Vault 路径")
@click.option("--api-url", "api_url", default="",
              help="MemoMind API 地址")
@click.option("--api-key", "api_key", default="",
              help="MemoMind API Key")
@click.option("--workspace", "workspace", default="default",
              help="MemoMind 工作区名称")
@click.option("--db", "db_path", type=click.Path(path_type=Path),
              help="MemoMind SQLite 数据库路径 (MCP 本地模式)")
@click.option("--temp-dir", "temp_dir", type=click.Path(path_type=Path),
              help="临时目录（默认系统临时目录）")
@click.option("--threshold", default=0.85, show_default=True,
              type=float, help="去重阈值")
@click.option("--min-score", default=30, show_default=True,
              type=int, help="最低价值评分")
@click.option("--simhash", is_flag=True,
              help="使用 SimHash 去重（大规模场景）")
@click.option("--merge", is_flag=True,
              help="启用版本合并")
@click.option("--incremental", is_flag=True,
              help="增量更新（仅处理变更文件）")
@click.option("--vision", is_flag=True,
              help="启用大模型图片识别（需要配置 API）")
@click.option("--vision-api-url", "vision_api_url", default="",
              help="大模型 API 地址（OpenAI 兼容）")
@click.option("--vision-api-key", "vision_api_key", default="",
              help="大模型 API Key")
@click.option("--vision-model", "vision_model", default="qwen-vl-plus",
              help="大模型名称")
@click.option("-v", "--verbose", is_flag=True,
              help="详细输出")
def pipeline(source_dir, final_output, target_type, vault_path, api_url, api_key, workspace, db_path,
             temp_dir, threshold, min_score, simhash, merge, incremental,
             vision, vision_api_url, vision_api_key, vision_model, verbose):
    """一键完成全流程（A → B → C → 导出）"""
    source_dir = source_dir.resolve()

    console.print(f"[bold green]Doc-Knowledge v{__version__} — pipeline[/bold green]")
    console.print(f"源目录: [cyan]{source_dir}[/cyan]")

    # 创建临时目录用于中间步骤
    if temp_dir:
        work_dir = Path(temp_dir) / "doc-knowledge-workspace"
    else:
        work_dir = Path(tempfile.mkdtemp(prefix="dck_"))

    work_dir.mkdir(parents=True, exist_ok=True)
    mirror_dir = work_dir / "mirror"
    extracted_dir = work_dir / "extracted"

    # 初始化视觉识别服务
    vision_service = None
    if vision and vision_api_key:
        api_url_v = vision_api_url or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        vision_service = LLMVisionService(
            api_url=api_url_v,
            api_key=vision_api_key,
            model=vision_model,
        )
        console.print(f"[dim]图片识别: {vision_model}[/dim]")
    elif vision and not vision_api_key:
        console.print("[yellow]警告：--vision 已启用但未提供 --vision-api-key，跳过图片识别[/yellow]")

    try:
        # Step 1: convert (A → B)
        console.print("\n[bold]Step 1/3: 转换 (A → B)[/bold]")
        _run_convert(source_dir, mirror_dir, verbose=verbose, vision_service=vision_service)

        # Step 2: extract (B → C)
        console.print("\n[bold]Step 2/3: 提取 (B → C)[/bold]")
        _run_extract(mirror_dir, extracted_dir, threshold=threshold,
                     min_score=min_score, simhash=simhash, merge=merge,
                     incremental=incremental, previous_output=final_output,
                     verbose=verbose)

        # Step 3: export (C → 目标)
        console.print(f"\n[bold]Step 3/3: 导出 (C → {target_type})[/bold]")
        if target_type == "obsidian":
            if not vault_path:
                console.print("[yellow]跳过 Obsidian 导出（未指定 --vault）[/yellow]")
            else:
                exporter = ObsidianExporter(vault_path)
                stats = exporter.export(extracted_dir)
                console.print(f"[green]导出 {stats['exported']} 个文件[/green]")
        elif target_type == "memomind":
            if db_path:
                exporter = MemoMindMCPExporter(db_path, workspace=workspace)
            elif api_url:
                exporter = MemoMindExporter(api_url, api_key=api_key, workspace=workspace)
            else:
                console.print("[yellow]跳过 MemoMind 导出（未指定 --api-url 或 --db）[/yellow]")
                exporter = None
            if exporter:
                try:
                    stats = exporter.export(extracted_dir)
                    console.print(f"[green]导出 {stats['exported']} 个文件到 MemoMind[/green]")
                except ConnectionError as e:
                    console.print(f"[yellow]{e}[/yellow]")
        else:
            if not final_output:
                final_output = source_dir.parent / f"{source_dir.name}_knowledge"
            exporter = MarkdownExporter(final_output)
            stats = exporter.export(extracted_dir)
            console.print(f"[green]导出 {stats['exported']} 个文件到 {final_output}[/green]")

        console.print("\n[bold green]Pipeline 完成！[/bold green]")

    finally:
        # 清理临时目录
        if not temp_dir:
            shutil.rmtree(work_dir, ignore_errors=True)


# ──────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────

def _run_convert(source_dir, output_dir, formats=None, recursive=True, verbose=False, vision_service=None):
    """convert 的内部逻辑（供 pipeline 调用）"""
    source_dir = source_dir.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    all_files = list(source_dir.rglob("*") if recursive else source_dir.iterdir())
    all_files = [f for f in all_files if f.is_file()]

    if not all_files:
        console.print("[yellow]未找到任何文件[/yellow]")
        return

    supported = set(get_supported_extensions())
    format_filter = set(f".{f.lower().lstrip('.')}" for f in (formats or [])) if formats else None

    to_convert = []
    to_copy = []
    to_skip = []

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

    stats = {"converted": 0, "copied": 0, "skipped": 0, "errors": 0, "images": 0}

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
                    source_file, 
                    output_dir=output_dir, 
                    vision_service=vision_service,
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
        dest = output_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        stats["kept"] += 1

    console.print(f"[dim]保留: {stats['kept']}, 去重: {len(duplicates)}, "
                  f"低分: {stats['low_score']}, 合并: {len([d for d in duplicates if 'merged_into' in d])}[/dim]")


def _add_extract_frontmatter(content: str, doc: dict) -> str:
    """在 frontmatter 中添加提取元数据（评分、标签等）"""
    import re
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


if __name__ == "__main__":
    main()
