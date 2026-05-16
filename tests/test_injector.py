"""测试 Markdown 注入器"""

import pytest
from pathlib import Path
from doc_knowledge.injector import MarkdownInjector, ConversionStats, COPY_AS_IS_EXTENSIONS


@pytest.fixture
def injector():
    return MarkdownInjector()


@pytest.fixture
def source_dir(tmp_path):
    """创建测试源目录"""
    src = tmp_path / "source"
    src.mkdir()
    return src


@pytest.fixture
def output_dir(tmp_path):
    """创建测试输出目录"""
    out = tmp_path / "output"
    out.mkdir()
    return out


def test_inject_converted_files(injector, source_dir, output_dir):
    """测试注入已转换的文件"""
    test_file = source_dir / "report.docx"
    test_file.write_text("dummy")
    
    content_map = {
        test_file: "# 测试报告\n\n内容..."
    }
    
    stats = injector.inject(source_dir, output_dir, content_map)
    
    assert stats.converted == 1
    assert (output_dir / "report.docx.md").exists()


def test_inject_creates_directory_structure(injector, source_dir, output_dir):
    """测试创建目录结构"""
    subdir = source_dir / "subdir"
    subdir.mkdir()
    test_file = subdir / "report.docx"
    test_file.write_text("dummy")
    
    content_map = {test_file: "# 内容"}
    injector.inject(source_dir, output_dir, content_map)
    
    assert (output_dir / "subdir" / "report.docx.md").exists()


def test_inject_copies_images(injector, source_dir, output_dir):
    """测试图片直接复制"""
    img_file = source_dir / "photo.png"
    img_file.write_bytes(b"\x89PNG\r\n\x1a\n")
    
    content_map = {}
    stats = injector.inject(source_dir, output_dir, content_map)
    
    assert stats.copied == 1
    assert (output_dir / "photo.png").exists()
    # 图片不应有 .md 包装文件
    assert not (output_dir / "photo.png.md").exists()


def test_inject_wraps_unsupported_files(injector, source_dir, output_dir):
    """测试不支持的文件创建元数据包装"""
    video_file = source_dir / "video.mp4"
    video_file.write_bytes(b"\x00" * 100)
    
    content_map = {}
    stats = injector.inject(source_dir, output_dir, content_map)
    
    assert stats.skipped == 1
    assert (output_dir / "video.mp4").exists()
    assert (output_dir / "video.mp4.md").exists()
    
    # 检查元数据包装内容
    wrapper = (output_dir / "video.mp4.md").read_text(encoding="utf-8")
    assert "video.mp4" in wrapper
    assert "source:" in wrapper


def test_inject_creates_summary(injector, source_dir, output_dir):
    """测试生成转换统计报告"""
    content_map = {}
    injector.inject(source_dir, output_dir, content_map)
    
    assert (output_dir / "summary.txt").exists()


def test_dry_run(injector, source_dir, output_dir):
    """测试 dry run 模式不写入文件"""
    test_file = source_dir / "report.docx"
    test_file.write_text("dummy")
    
    content_map = {test_file: "# 内容"}
    stats = injector.inject(source_dir, output_dir, content_map, dry_run=True)
    
    assert stats.converted == 1
    assert not (output_dir / "report.docx.md").exists()
    assert not (output_dir / "summary.txt").exists()


def test_conversion_stats_summary():
    """测试统计摘要输出"""
    stats = ConversionStats()
    stats.converted = 10
    stats.copied = 3
    stats.skipped = 2
    stats.errors = 1
    
    summary = stats.summary()
    assert "10" in summary
    assert "3" in summary
    assert "2" in summary
    assert "1" in summary
