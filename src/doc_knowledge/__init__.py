"""
Doc-Knowledge: 文档知识提取工具

将 Office 文档（PDF/PPT/DOCX/XLSX）批量转换为结构化 Markdown 知识库，
支持去重、价值提取，并导出到 Obsidian 或 MemoMind。
"""

__version__ = "0.1.0"

from .converters import BaseConverter, DocxConverter, PdfConverter, get_converter_registry, find_converter
from .injector import MarkdownInjector, ConversionStats

__all__ = [
    "__version__",
    "BaseConverter",
    "DocxConverter",
    "PdfConverter",
    "get_converter_registry",
    "find_converter",
    "MarkdownInjector",
    "ConversionStats",
]
