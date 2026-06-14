"""extract 命令 (B → C)"""

from pathlib import Path

import click

from doc_knowledge import __version__
from doc_knowledge.cli._helpers import console, _add_extract_frontmatter
from doc_knowledge.extractors.deduplicator import Deduplicator
from doc_knowledge.extractors.scorer import ValueScorer
from doc_knowledge.extractors.tagger import Tagger
from doc_knowledge.extractors.merger import VersionMerger
from doc_knowledge.extractors.simhash_dedup import SimHashDeduplicator


@click.command("extract")
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
