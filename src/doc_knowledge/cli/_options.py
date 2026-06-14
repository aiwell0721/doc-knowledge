"""共享 click 选项装饰器

仅收纳出现在 2+ 个命令中的选项；单命令独有选项保留在命令文件内。
"""

from pathlib import Path

import click


def ocr_options(f):
    """OCR 相关 4 个选项（convert / pipeline 共用）"""
    f = click.option("--ocr-model", "ocr_model", default="",
                     help="OCR 模型名称")(f)
    f = click.option("--ocr-api-key", "ocr_api_key", default="",
                     help="OCR API Key")(f)
    f = click.option("--ocr-api-url", "ocr_api_url", default="",
                     help="OCR API 地址（OpenAI 兼容）")(f)
    f = click.option("--ocr", "ocr_mode",
                     type=click.Choice(["cloud", "local"]),
                     help="OCR 模式（hybrid 尚未实现）")(f)
    return f


def memomind_options(f):
    """MemoMind 导出相关选项（export / pipeline 共用）"""
    f = click.option("--db", "db_path", type=click.Path(path_type=Path),
                     help="MemoMind SQLite 数据库路径 (MCP 本地模式)")(f)
    f = click.option("--workspace", "workspace", default="default",
                     help="MemoMind 工作区名称")(f)
    f = click.option("--api-key", "api_key", default="",
                     help="MemoMind API Key")(f)
    f = click.option("--api-url", "api_url", default="",
                     help="MemoMind API 地址")(f)
    return f


def memomind_post_options(f):
    """MemoMind 后处理选项（export / pipeline 共用）"""
    f = click.option("--dedup", "run_dedup", is_flag=True,
                     help="导出后运行 TF-IDF 语义去重扫描")(f)
    f = click.option("--consolidate", "run_consolidate", is_flag=True,
                     help="导出后运行知识整理建议（主题聚类/合并/陈旧检测）")(f)
    return f
