"""pipeline 命令 (A → B → C → 导出)"""

import shutil
import tempfile
from pathlib import Path

import click

from doc_knowledge import __version__
from doc_knowledge.cli._helpers import (
    console,
    _setup_ocr,
    _run_convert,
    _run_extract,
    _run_memomind_post_processing,
)
from doc_knowledge.cli._options import ocr_options, memomind_options, memomind_post_options
from doc_knowledge.exporters.obsidian import ObsidianExporter, MarkdownExporter
from doc_knowledge.exporters.memomind import MemoMindExporter, MemoMindMCPExporter


@click.command("pipeline")
@click.argument("source_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("-o", "--output", "final_output", type=click.Path(path_type=Path),
              help="最终输出目录")
@click.option("-t", "--target", "target_type",
              type=click.Choice(["obsidian", "markdown", "memomind"]),
              default="markdown", show_default=True,
              help="导出目标")
@click.option("--vault", "vault_path", type=click.Path(path_type=Path),
              help="Obsidian Vault 路径")
@memomind_options
@memomind_post_options
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
@ocr_options
@click.option("-v", "--verbose", is_flag=True,
              help="详细输出")
def pipeline(source_dir, final_output, target_type, vault_path,
             api_url, api_key, workspace, db_path,
             run_dedup, run_consolidate,
             temp_dir, threshold, min_score, simhash, merge, incremental,
             ocr_mode, ocr_api_url, ocr_api_key, ocr_model, verbose):
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

    # OCR 服务（统一管道，处理嵌入图片 + 扫描型 PDF）
    ocr_service = _setup_ocr(ocr_mode, ocr_api_url, ocr_api_key, ocr_model)

    try:
        # Step 1: convert (A → B)
        console.print("\n[bold]Step 1/3: 转换 (A → B)[/bold]")
        _run_convert(source_dir, mirror_dir, verbose=verbose,
                     ocr_service=ocr_service)

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
                    # MemoMind 后处理
                    if db_path and (run_dedup or run_consolidate):
                        _run_memomind_post_processing(db_path, workspace, run_dedup, run_consolidate)
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
