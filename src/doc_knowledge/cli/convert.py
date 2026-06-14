"""convert 命令 (A → B)"""

from pathlib import Path

import click

from doc_knowledge import __version__
from doc_knowledge.cli._helpers import console, _setup_ocr, _run_convert
from doc_knowledge.cli._options import ocr_options


@click.command("convert")
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
@ocr_options
@click.option("-v", "--verbose", is_flag=True,
              help="详细输出")
def convert(source_dir, output_dir, formats, recursive, overwrite, dry_run,
            ocr_mode, ocr_api_url, ocr_api_key, ocr_model, verbose):
    """将文档转换为 Markdown 镜像（A → B）"""
    source_dir = source_dir.resolve()
    if output_dir is None:
        output_dir = source_dir.parent / f"{source_dir.name}_mirror"
    output_dir = output_dir.resolve()

    console.print(f"[bold green]Doc-Knowledge v{__version__} — convert[/bold green]")
    console.print(f"源目录: [cyan]{source_dir}[/cyan]")
    console.print(f"输出目录: [cyan]{output_dir}[/cyan]")

    # OCR 服务（统一管道，处理嵌入图片 + 扫描型 PDF）
    ocr_service = _setup_ocr(ocr_mode, ocr_api_url, ocr_api_key, ocr_model)

    stats = _run_convert(
        source_dir, output_dir,
        formats=list(formats) if formats else None,
        recursive=recursive, verbose=verbose,
        ocr_service=ocr_service,
        dry_run=dry_run,
    )

    if dry_run:
        for f in stats.get("to_convert", []):
            console.print(f"  [MD] {f.relative_to(source_dir)}")
        for f in stats.get("to_copy", []):
            console.print(f"  [CP] {f.relative_to(source_dir)}")
        return

    console.print()
    console.print(f"[bold green]完成！转换 {stats['converted']}, 图片 {stats['images']}, "
                  f"复制 {stats['copied']}, 跳过 {stats['skipped']}, 错误 {stats['errors']}[/bold green]")
