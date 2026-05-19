"""测试导出器"""

import tempfile
from pathlib import Path
from doc_knowledge.exporters.obsidian import ObsidianExporter, MarkdownExporter


def test_markdown_exporter():
    """Markdown 导出器应该复制文件"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建测试知识目录
        knowledge = Path(tmpdir) / "knowledge"
        knowledge.mkdir()
        (knowledge / "test.md").write_text("# Test\n\nHello world", encoding="utf-8")

        # 导出
        output = Path(tmpdir) / "output"
        exporter = MarkdownExporter(output)
        stats = exporter.export(knowledge)

        assert stats["exported"] == 1
        assert (output / "test.md").exists()


def test_obsidian_exporter():
    """Obsidian 导出器应该添加 frontmatter"""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir) / "vault"
        vault.mkdir()
        knowledge = Path(tmpdir) / "knowledge"
        knowledge.mkdir()

        content = "# Test\n\nHello world"
        (knowledge / "test.md").write_text(content, encoding="utf-8")

        exporter = ObsidianExporter(vault)
        stats = exporter.export(knowledge)

        assert stats["exported"] == 1
        output_file = vault / "doc-knowledge" / "test.md"
        assert output_file.exists()
        result = output_file.read_text(encoding="utf-8")
        assert "---" in result  # 应该有 frontmatter


def test_obsidian_exporter_preserves_frontmatter():
    """Obsidian 导出器应该保留现有 frontmatter"""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir) / "vault"
        vault.mkdir()
        knowledge = Path(tmpdir) / "knowledge"
        knowledge.mkdir()

        content = """---
title: "Test"
tags: [architecture]
---

# Test content
"""
        (knowledge / "test.md").write_text(content, encoding="utf-8")

        exporter = ObsidianExporter(vault)
        stats = exporter.export(knowledge)

        result = (vault / "doc-knowledge" / "test.md").read_text(encoding="utf-8")
        assert "architecture" in result
        assert "tags:" in result
