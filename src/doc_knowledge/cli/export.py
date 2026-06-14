"""export 命令 (C → 目标)"""

from pathlib import Path

import click

from doc_knowledge import __version__
from doc_knowledge.cli._helpers import console, _run_memomind_post_processing
from doc_knowledge.cli._options import memomind_options, memomind_post_options
from doc_knowledge.exporters.obsidian import ObsidianExporter, MarkdownExporter
from doc_knowledge.exporters.memomind import MemoMindExporter, MemoMindMCPExporter


@click.command("export")
@click.argument("knowledge_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("-t", "--target", "target_type",
              type=click.Choice(["obsidian", "markdown", "memomind"]),
              default="markdown", show_default=True,
              help="导出目标")
@click.option("--vault", "vault_path", type=click.Path(path_type=Path),
              help="Obsidian Vault 路径 (target=obsidian 时必填)")
@click.option("-o", "--output", "output_dir", type=click.Path(path_type=Path),
              help="输出目录 (target=markdown 时)")
@memomind_options
@memomind_post_options
def export_cmd(knowledge_dir, target_type, vault_path, output_dir,
               api_url, api_key, workspace, db_path,
               run_dedup, run_consolidate):
    """导出知识文档到目标系统（C → 目标）"""
    knowledge_dir = knowledge_dir.resolve()

    console.print(f"[bold green]Doc-Knowledge v{__version__} — export[/bold green]")
    console.print(f"知识目录: [cyan]{knowledge_dir}[/cyan]")
    console.print(f"目标: [cyan]{target_type}[/cyan]")

    if target_type == "obsidian":
        if not vault_path:
            console.print("[red]错误：--vault 是必填项（Obsidian Vault 路径）[/red]")
            raise click.exceptions.Exit(1)
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
            raise click.exceptions.Exit(1)
        try:
            stats = exporter.export(knowledge_dir)
        except ConnectionError as e:
            console.print(f"[red]{e}[/red]")
            raise click.exceptions.Exit(1)
    else:
        console.print(f"[red]未知目标: {target_type}[/red]")
        raise click.exceptions.Exit(1)

    console.print(f"[bold green]导出完成！成功 {stats['exported']}, 错误 {stats['errors']}[/bold green]")
    if stats.get("error_details"):
        for detail in stats["error_details"]:
            console.print(f"  [red]X {detail}[/red]")

    # MemoMind 后处理（仅在 db_path 指定时可用）
    if target_type == "memomind" and db_path and (run_dedup or run_consolidate):
        _run_memomind_post_processing(db_path, workspace, run_dedup, run_consolidate)
