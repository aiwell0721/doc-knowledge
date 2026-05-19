"""测试 MarkItDown 转换器封装"""

import tempfile
from pathlib import Path

from doc_knowledge.converters import convert_file, get_supported_extensions


def test_supported_extensions():
    """支持格式列表非空"""
    exts = get_supported_extensions()
    assert len(exts) > 10
    assert ".pdf" in exts
    assert ".docx" in exts
    assert ".pptx" in exts
    assert ".xlsx" in exts


def test_convert_txt_file():
    """纯文本文件转换"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("Hello, this is a test document.\nSecond line.\n")
        f.flush()
        result = convert_file(Path(f.name))
        markdown = result[0] if isinstance(result, tuple) else result
    
    assert "Hello" in markdown
    assert "test document" in markdown


def test_convert_nonexistent_file():
    """不存在的文件应抛出 FileNotFoundError"""
    import pytest
    with pytest.raises(FileNotFoundError):
        convert_file(Path("/nonexistent/file.txt"))


def test_convert_csv_file():
    """CSV 文件转换"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write("name,age,city\nAlice,30,Beijing\nBob,25,Shanghai\n")
        f.flush()
        result = convert_file(Path(f.name))
        markdown = result[0] if isinstance(result, tuple) else result
    
    assert "Alice" in markdown or "name" in markdown
