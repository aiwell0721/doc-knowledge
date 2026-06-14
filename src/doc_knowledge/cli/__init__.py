"""
Doc-Knowledge CLI 入口

5 个命令覆盖全链路：convert / extract / export / pipeline / webui

通过 `from doc_knowledge.cli import main` 取主入口（兼容旧版单文件 cli.py）。
"""

import click

from doc_knowledge import __version__
from doc_knowledge.cli.convert import convert
from doc_knowledge.cli.extract import extract
from doc_knowledge.cli.export import export_cmd
from doc_knowledge.cli.pipeline import pipeline
from doc_knowledge.cli.webui import webui


@click.group()
@click.version_option(version=__version__, prog_name="doc-knowledge")
def main():
    """Doc-Knowledge: 文档知识提取工具"""
    pass


main.add_command(convert)
main.add_command(extract)
main.add_command(export_cmd)
main.add_command(pipeline)
main.add_command(webui)


__all__ = ["main"]


if __name__ == "__main__":
    main()
