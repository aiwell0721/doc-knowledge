"""测试工具函数"""

from pathlib import Path
from doc_knowledge.utils import make_frontmatter


def test_make_frontmatter_basic():
    """测试基本 frontmatter 生成"""
    result = make_frontmatter(
        title="test.pdf",
        source_path=Path("/docs/test.pdf"),
        original_format="pdf",
    )
    
    assert 'title: "test.pdf"' in result
    assert 'original_format: "pdf"' in result
    assert 'conversion_status: "converted"' in result
    assert 'source: "file://' in result
    assert 'test.pdf' in result
    assert result.startswith("---")


def test_make_frontmatter_skipped():
    """测试跳过状态的 frontmatter"""
    result = make_frontmatter(
        title="video.mp4",
        source_path=Path("/docs/video.mp4"),
        original_format="mp4",
        conversion_status="skipped",
        file_size="256 MB",
    )
    
    assert "⚠️" in result
    assert "暂不支持转换" in result
    assert 'file_size: "256 MB"' in result


def test_make_frontmatter_with_extra():
    """测试额外字段"""
    result = make_frontmatter(
        title="test.pdf",
        source_path=Path("/docs/test.pdf"),
        extra={"custom": "value"},
    )
    
    assert 'custom: "value"' in result
