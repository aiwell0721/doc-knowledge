"""
PDF 转 Markdown 转换器
"""

from pathlib import Path
from typing import ClassVar

from .base import BaseConverter


class PdfConverter(BaseConverter):
    """PDF 转 Markdown 转换器
    
    使用 PyMuPDF (fitz) 提取 PDF 文本。
    Phase 1: 仅文本提取（按页）。
    Phase 2: 表格检测、图片提取。
    """
    
    supported_extensions: ClassVar[list[str]] = [".pdf"]
    
    def convert(self, filepath: Path) -> str:
        """
        将 PDF 文件转换为 Markdown
        
        Args:
            filepath: PDF 文件路径
            
        Returns:
            Markdown 内容字符串（按页组织）
        """
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ImportError(
                "PyMuPDF 未安装。请运行: pip install doc-knowledge[pdf]"
            )
        
        doc = fitz.open(str(filepath))
        parts: list[str] = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")
            
            if text.strip():
                parts.append(f"## Page {page_num + 1}\n\n{text.strip()}")
        
        doc.close()
        
        if not parts:
            return "# 此 PDF 无文本内容\n"
        
        return "\n\n".join(parts)
