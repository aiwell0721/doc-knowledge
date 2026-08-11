"""extract 命令 (B → C)"""

from pathlib import Path

import click

from doc_knowledge import __version__
from doc_knowledge.cli._helpers import (
    console,
    _collect_documents,
    _dedup_and_merge,
    _write_extracted,
)


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

    # 收集 + 评分 + 打标签（与 pipeline 共用核心逻辑）
    documents = _collect_documents(mirror_dir, min_score)
    if not documents:
        console.print("[yellow]未找到 Markdown 文件[/yellow]")
        return

    console.print(f"找到 [cyan]{len(documents)}[/cyan] 个 Markdown 文件")
    console.print(f"评分完成 — 通过: {sum(1 for d in documents if d['score'] >= min_score)} / "
                  f"淘汰: {sum(1 for d in documents if d['score'] < min_score)}")

    # 去重 + 版本合并
    if simhash:
        console.print("[dim]使用 SimHash 去重...[/dim]")
    kept, duplicates = _dedup_and_merge(documents, threshold=threshold,
                                        simhash=simhash, merge=merge)
    console.print(f"去重完成 — 保留: {len(kept)}, 重复: {len(duplicates)}")
    if merge:
        console.print(f"[dim]版本合并 — 合并: "
                      f"{len([d for d in duplicates if 'merged_into' in d])}[/dim]")

    if dry_run:
        console.print("\n[bold]Dry Run — 计划:[/bold]")
        for d in kept:
            console.print(f"  [green]保留[/green] {d['path'].relative_to(mirror_dir)} "
                          f"(score={d['score']}, tags={d['tags']})")
        for d in duplicates:
            console.print(f"  [yellow]去重[/yellow] {d['path'].relative_to(mirror_dir)} "
                          f"→ similar to {d['similar_to'].name}")
        return

    stats = _write_extracted(kept, duplicates, mirror_dir, output_dir, min_score,
                             keep_deprecated=keep_deprecated, verbose=verbose)

    console.print()
    console.print(f"[bold green]提取完成！保留 {stats['kept']}, 去重 {stats['deduped']}, "
                  f"低分 {stats['low_score']}, 错误 {stats['errors']}[/bold green]")
