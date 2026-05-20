"""
Tests for converters/base.py — BaseConverter abstract class.

Covers:
- Abstract method enforcement
- can_handle() method
- get_output_filename() method
"""

import pytest
from pathlib import Path
from abc import ABC
from doc_knowledge.converters.base import BaseConverter


# ── Concrete test subclass ──

class DummyConverter(BaseConverter):
    """Minimal concrete converter for testing."""
    supported_extensions = [".dummy", ".test"]

    def convert(self, filepath: Path) -> str:
        return f"converted: {filepath.name}"


class IncompleteConverter(BaseConverter):
    """Converter that does NOT implement convert() — should fail to instantiate."""
    supported_extensions = [".foo"]


# ── Tests ──

class TestBaseConverterIsAbstract:
    """BaseConverter 是抽象类，不能直接实例化"""

    def test_cannot_instantiate_base(self):
        """抽象类 BaseConverter 无法直接实例化"""
        with pytest.raises(TypeError):
            BaseConverter()

    def test_incomplete_converter_fails(self):
        """不实现 convert() 的子类无法实例化"""
        with pytest.raises(TypeError):
            IncompleteConverter()

    def test_concrete_converter_instantiates(self):
        """实现 convert() 的子类可以正常实例化"""
        conv = DummyConverter()
        assert isinstance(conv, BaseConverter)
        assert isinstance(conv, ABC)


class TestSupportedExtensions:
    """子类必须定义 supported_extensions"""

    def test_dummy_extensions(self):
        conv = DummyConverter()
        assert ".dummy" in conv.supported_extensions
        assert ".test" in conv.supported_extensions


class TestCanHandle:
    """can_handle() 方法根据扩展名判断"""

    def test_handles_known_extension(self):
        conv = DummyConverter()
        assert conv.can_handle(Path("file.dummy")) is True
        assert conv.can_handle(Path("file.test")) is True

    def test_rejects_unknown_extension(self):
        conv = DummyConverter()
        assert conv.can_handle(Path("file.pdf")) is False
        assert conv.can_handle(Path("file.docx")) is False

    def test_case_insensitive(self):
        conv = DummyConverter()
        assert conv.can_handle(Path("file.DUMMY")) is True
        assert conv.can_handle(Path("file.TEST")) is True

    def test_path_with_deep_nesting(self):
        conv = DummyConverter()
        assert conv.can_handle(Path("/a/b/c/file.dummy")) is True

    def test_no_extension(self):
        conv = DummyConverter()
        assert conv.can_handle(Path("noext")) is False


class TestGetOutputFilename:
    """get_output_filename() 生成输出文件名"""

    def test_simple_name(self):
        conv = DummyConverter()
        assert conv.get_output_filename(Path("report.dummy")) == "report.dummy.md"

    def test_nested_path(self):
        conv = DummyConverter()
        result = conv.get_output_filename(Path("/docs/my report.test"))
        assert result == "my report.test.md"

    def test_preserves_dots_in_name(self):
        conv = DummyConverter()
        # filename with dots before extension
        assert conv.get_output_filename(Path("v2.final.dummy")) == "v2.final.dummy.md"

    def test_chinese_characters(self):
        conv = DummyConverter()
        result = conv.get_output_filename(Path("测试文档.dummy"))
        assert result == "测试文档.dummy.md"


class TestConvertMethod:
    """convert() 调用具体实现"""

    def test_convert_returns_result(self, tmp_path):
        conv = DummyConverter()
        fake_file = tmp_path / "sample.dummy"
        fake_file.touch()
        result = conv.convert(fake_file)
        assert "converted" in result
        assert "sample.dummy" in result
