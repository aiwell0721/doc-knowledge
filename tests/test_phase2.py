"""测试 Phase 2 新增功能：SimHash 去重、版本合并、MemoMind 导出"""

import tempfile
import sqlite3
from pathlib import Path

from doc_knowledge.extractors.simhash_dedup import SimHashDeduplicator
from doc_knowledge.extractors.merger import VersionMerger
from doc_knowledge.exporters.memomind import MemoMindMCPExporter


def _make_doc(content: str, score: int = 50, name: str = "test") -> dict:
    return {"path": Path(f"{name}.md"), "content": content, "score": score}


# ──────────────────────────────────────────────
# SimHash 去重测试
# ──────────────────────────────────────────────

def test_simhash_identical_documents():
    """相同文档应该被 SimHash 识别为重复"""
    content = "这是一个测试文档，包含一些关于机器学习和人工智能的内容"
    docs = [_make_doc(content, 50), _make_doc(content, 60)]
    kept, dups = SimHashDeduplicator(threshold=3).deduplicate(docs)
    assert len(kept) == 1
    assert len(dups) == 1
    assert kept[0]["score"] == 60


def test_simhash_different_documents():
    """不同文档应该保留"""
    docs = [
        _make_doc("机器学习是人工智能的重要分支", 50),
        _make_doc("今天天气很好适合出去散步", 50),
    ]
    kept, dups = SimHashDeduplicator(threshold=3).deduplicate(docs)
    assert len(kept) == 2
    assert len(dups) == 0


def test_simhash_empty_list():
    """空列表应该返回空"""
    kept, dups = SimHashDeduplicator().deduplicate([])
    assert kept == []
    assert dups == []


# ──────────────────────────────────────────────
# 版本合并测试
# ──────────────────────────────────────────────

def test_version_merge():
    """同一文档的多个版本应该合并"""
    docs = [
        _make_doc("内容 v1", 40, "report_v1.md"),
        _make_doc("内容 v2 更长更完整", 60, "report_v2.md"),
        _make_doc("其他内容", 50, "other.md"),
    ]
    merger = VersionMerger()
    kept, merged = merger.merge(docs)
    assert len(kept) == 2  # report_v2 + other
    assert len(merged) == 1  # report_v1


def test_version_merge_single():
    """单一版本不需要合并"""
    docs = [_make_doc("content", 50, "single.md")]
    kept, merged = VersionMerger().merge(docs)
    assert len(kept) == 1
    assert len(merged) == 0


def test_version_select_best():
    """应该选择评分更高的版本"""
    docs = [
        _make_doc("short", 40, "doc_v1.md"),
        _make_doc("longer and more detailed content", 60, "doc_v2.md"),
    ]
    kept, _ = VersionMerger().merge(docs)
    # Path.name 是 doc_v2.md（因为 _make_doc 传入的就是完整文件名）
    assert "doc_v2" in kept[0]["path"].name


def test_strip_version():
    """版本号应该从文件名中去除"""
    merger = VersionMerger()
    # 核心功能：版本号被去除
    result = merger._strip_version("report_v1.md")
    assert "v1" not in result


# ──────────────────────────────────────────────
# MemoMind MCP 导出测试
# ──────────────────────────────────────────────

def test_memomind_mcp_export():
    """MemoMind MCP 导出器应该能写入 SQLite"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建最小 MemoMind 数据库
        db_path = Path(tmpdir) / "memomind.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workspaces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                created_at INTEGER
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id INTEGER,
                title TEXT,
                content TEXT,
                created_at INTEGER,
                updated_at INTEGER
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS note_tags (
                note_id INTEGER,
                tag_id INTEGER,
                PRIMARY KEY (note_id, tag_id)
            )
        """)
        conn.commit()
        conn.close()

        # 创建测试知识
        knowledge = Path(tmpdir) / "knowledge"
        knowledge.mkdir()
        (knowledge / "test.md").write_text(
            '---\ntitle: "Test Note"\ndk_tags: ["test", "demo"]\n---\n\nHello world',
            encoding="utf-8",
        )

        # 导出
        exporter = MemoMindMCPExporter(db_path, workspace="default")
        stats = exporter.export(knowledge)

        assert stats["exported"] == 1
        assert stats["errors"] == 0

        # 验证数据库
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM notes")
        assert cursor.fetchone()[0] == 1
        cursor.execute("SELECT title FROM notes")
        assert cursor.fetchone()[0] == "Test Note"
        conn.close()
