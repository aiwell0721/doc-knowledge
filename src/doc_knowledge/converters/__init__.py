"""文档转换器包"""

from .base import BaseConverter
from .docx_converter import DocxConverter
from .pdf_converter import PdfConverter

# 注册所有转换器
CONVERTER_REGISTRY: list[type[BaseConverter]] = [
    DocxConverter,
    PdfConverter,
]


def get_converter_registry() -> list[type[BaseConverter]]:
    """获取转换器注册表"""
    return list(CONVERTER_REGISTRY)


def find_converter(filepath) -> BaseConverter | None:
    """
    查找能处理指定文件的转换器
    
    Args:
        filepath: 文件路径 (Path 或 str)
        
    Returns:
        匹配的转换器实例，如果没有则返回 None
    """
    from pathlib import Path
    
    path = Path(filepath) if not isinstance(filepath, Path) else filepath
    
    for converter_cls in CONVERTER_REGISTRY:
        converter = converter_cls()
        if converter.can_handle(path):
            return converter
    
    return None
