"""
Doc-Knowledge CLI 入口

6 个命令覆盖全链路：convert / extract / export / pipeline / retry-slide / webui

通过 `from doc_knowledge.cli import main` 取主入口（兼容旧版单文件 cli.py）。
"""

import logging

import click

from doc_knowledge import __version__
from doc_knowledge.cli.convert import convert
from doc_knowledge.cli.extract import extract
from doc_knowledge.cli.export import export_cmd
from doc_knowledge.cli.pipeline import pipeline
from doc_knowledge.cli.retry_slide import retry_slide
from doc_knowledge.cli.webui import webui


@click.group()
@click.version_option(version=__version__, prog_name="doc-knowledge")
@click.option("--log-level", default="WARNING", show_default=True,
              type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"],
                                case_sensitive=False),
              help="日志级别（输出到 stderr）")
def main(log_level):
    """Doc-Knowledge: 文档知识提取工具"""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(levelname)s %(name)s: %(message)s",
    )


main.add_command(convert)
main.add_command(extract)
main.add_command(export_cmd)
main.add_command(pipeline)
main.add_command(retry_slide)
main.add_command(webui)


__all__ = ["main"]


if __name__ == "__main__":
    main()
