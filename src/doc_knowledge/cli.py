"""
Doc-Knowledge CLI 入口
"""

import click
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from doc_knowledge import (
    __version__,
    find_converter,
    MarkdownInjector,
    ConversionStats,
)
from doc_knowledge.utils import make_frontmatter
from doc_knowledge.injector import CONVERTIBLE_EXTENSIONS, COPY_AS_IS_EXTENSIONS


console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="doc-knowledge")
def main():
    """Doc-Knowledge: 文档知识提取工具"""
    pass


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
@click.option("-v", "--verbose", is_flag=True,
              help="详细输出")
def convert(source_dir, output_dir, formats, recursive, overwrite, dry_run, verbose):
    """
    将目录中的文档转换为 Markdown 镜像（A → B）
    
    支持格式: PDF, DOCX（Phase 1）
    PPTX, XLSX（Phase 2+）
    """
    source_dir = source_dir.resolve()
    if output_dir is None:
        output_dir = source_dir.parent / f"{source_dir.name}_mirror"
    output_dir = output_dir.resolve()
    
    console.print(f"[bold green]Doc-Knowledge 转换工具 v{__version__}[/bold green]")
    console.print(f"源目录: [cyan]{source_dir}[/cyan]")
    console.print(f"输出目录: [cyan]{output_dir}[/cyan]")
    console.print()
    
    # 扫描文件
    files = list(source_dir.rglob("*") if recursive else source_dir.iterdir())
    files = [f for f in files if f.is_file()]
    
    if not files:
        console.print("[yellow]未找到任何文件[/yellow]")
        return
    
    # 分类文件
    to_convert = []       # 需要转换的文件
    to_copy = []          # 直接复制的文件（图片）
    to_wrap = []          # 需要元数据包装的文件
    
    format_filter = set(f.lower() for f in formats) if formats else None
    
    for f in sorted(files):
        ext = f.suffix.lower()
        
        if format_filter and ext.lstrip(".") not in format_filter and ext not in format_filter:
            continue
        
        if ext in CONVERTIBLE_EXTENSIONS:
            # 检查是否有可用转换器
            converter = find_converter(f)
            if converter:
                to_convert.append(f)
            else:
                to_wrap.append(f)
        elif ext in COPY_AS_IS_EXTENSIONS:
            to_copy.append(f)
        else:
            to_wrap.append(f)
    
    if verbose or dry_run:
        console.print(f"[dim]可转换: {len(to_convert)}, 图片: {len(to_copy)}, 其他: {len(to_wrap)}[/dim]")
        if dry_run:
            console.print()
            console.print("[bold]Dry Run - 将要处理:[/bold]")
            for f in to_convert:
                console.print(f"  [MD] {f.relative_to(source_dir)} -> .md")
            for f in to_copy:
                console.print(f"  [CP] {f.relative_to(source_dir)} -> (复制)")
            for f in to_wrap:
                console.print(f"  [SK] {f.relative_to(source_dir)} -> (元数据包装)")
            return
    
    # 执行转换
    content_map = {}
    stats = ConversionStats()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("转换中...", total=len(to_convert))
        
        for source_file in to_convert:
            rel = source_file.relative_to(source_dir)
            progress.update(task, description=f"转换: {rel}")
            
            try:
                converter = find_converter(source_file)
                if converter:
                    markdown = converter.convert(source_file)
                    # 添加 frontmatter
                    frontmatter = make_frontmatter(
                        title=source_file.name,
                        source_path=source_file.resolve(),
                        source_relative=str(rel),
                        original_format=source_file.suffix.lstrip("."),
                    )
                    content_map[source_file] = frontmatter + markdown
            except Exception as e:
                stats.errors += 1
                stats.error_details.append(f"{rel}: {e}")
                if verbose:
                    console.print(f"[red]  ✗ {rel}: {e}[/red]")
            
            progress.advance(task)
    
    # 注入目录
    injector = MarkdownInjector()
    result = injector.inject(source_dir, output_dir, content_map, dry_run=dry_run)
    
    # 合并统计
    stats.converted = result.converted
    stats.copied = result.copied
    stats.skipped = result.skipped
    
    # 输出结果
    console.print()
    console.print(f"[bold green]{stats.summary()}[/bold green]")
    console.print()
    console.print(f"[dim]输出目录: {output_dir}[/dim]")


if __name__ == "__main__":
    main()
