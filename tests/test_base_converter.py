"""测试转换器基类"""

import pytest
from pathlib import Path
from doc_knowledge.converters.base import BaseConverter


class ConcreteConverter(BaseConverter):
    """用于测试的具体转换器"""
    supported_extensions = [".test"]
    
    def convert(self, filepath: Path) -> str:
        return f"# {filepath.name}\nConverted content"


def test_can_handle_matching_extension(tmp_path):
    """测试能处理匹配的扩展名"""
    converter = ConcreteConverter()
    test_file = tmp_path / "example.test"
    test_file.write_text("test")
    
    assert converter.can_handle(test_file) is True


def test_cannot_handle_non_matching_extension(tmp_path):
    """测试不能处理不匹配的扩展名"""
    converter = ConcreteConverter()
    test_file = tmp_path / "example.pdf"
    test_file.write_text("test")
    
    assert converter.can_handle(test_file) is False


def test_get_output_filename():
    """测试输出文件名生成"""
    converter = ConcreteConverter()
    name = converter.get_output_filename(Path("report.docx"))
    assert name == "report.docx.md"


def test_convert_returns_markdown(tmp_path):
    """测试转换返回 Markdown"""
    converter = ConcreteConverter()
    test_file = tmp_path / "example.test"
    test_file.write_text("test content")
    
    result = converter.convert(test_file)
    assert "# example.test" in result
    assert "Converted content" in result
