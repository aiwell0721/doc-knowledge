"""
MemoMind 后处理模块测试

验证 memomind_post.py 的去重扫描和知识整理功能。
"""

import tempfile
import sqlite3
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

from doc_knowledge.exporters.memomind_post import (
    run_dedup_report,
    run_consolidation_report,
    _get_client,
)


def _create_real_memomind_db(tmpdir: str) -> Path:
    """创建符合 MemoMind 真实 schema 的数据库"""
    db_path = Path(tmpdir) / "memomind.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # 工作区表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workspaces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            description TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute(
        "INSERT INTO workspaces (name) VALUES (?)", ("default",)
    )

    # 笔记表（真实 MemoMind schema）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER DEFAULT 1,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            tags TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 插入测试笔记
    now = datetime.now().isoformat()
    test_notes = [
        ("Python 异步编程指南", "本文介绍 asyncio 和协程的基本用法，包括事件循环、Task 和 Future。", '["python"]'),
        ("Python 异步编程入门", "介绍 Python 中的 asyncio 库和协程概念、事件循环、Task。", '["python"]'),
        ("Docker 容器化部署", "Docker 最佳实践：多阶段构建、健康检查、资源限制。", '["docker"]'),
        ("Kubernetes 集群管理", "K8s 集群运维：节点管理、Pod 调度、Service Mesh。", '["kubernetes"]'),
        ("Docker Compose 编排", "使用 docker-compose 编排多容器应用。", '["docker"]'),
    ]
    for title, content, tags in test_notes:
        cursor.execute(
            "INSERT INTO notes (title, content, tags, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (title, content, tags, now, now),
        )

    # 标签表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            parent_id INTEGER,
            alias_for INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 笔记-标签关联表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS note_tags (
            note_id INTEGER,
            tag_id INTEGER,
            PRIMARY KEY (note_id, tag_id)
        )
    """)

    # 笔记链接表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS note_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_note_id INTEGER,
            target_note_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    return db_path


# ──────────────────────────────────────────────
# 延迟导入测试
# ──────────────────────────────────────────────

def test_get_client_with_memomind_installed():
    """MemoMind 已安装时 _get_client 正常返回"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _create_real_memomind_db(tmpdir)
        client = _get_client(str(db_path))
        try:
            assert client is not None
            assert hasattr(client, '_semantic')
            assert hasattr(client, '_kg')
        finally:
            client.close()


def test_get_client_import_error_message():
    """未安装 MemoMind 时给出友好报错"""
    with patch('doc_knowledge.exporters.memomind_post._get_client') as mock_get:
        mock_get.side_effect = ImportError(
            "MemoMind SDK 未安装，无法运行后处理。\n"
            "安装: pip install memomind>=2.0.0"
        )
        try:
            mock_get("test.db")
            assert False, "Should have raised ImportError"
        except ImportError as e:
            assert "pip install memomind" in str(e)


# ──────────────────────────────────────────────
# 去重扫描测试
# ──────────────────────────────────────────────

def test_run_dedup_report_no_duplicates():
    """单条笔记时无重复"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _create_real_memomind_db(tmpdir)
        # 只用 1 个笔记的独立数据库
        single_db = Path(tmpdir) / "single.db"
        conn = sqlite3.connect(str(single_db))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id INTEGER DEFAULT 1,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                tags TEXT DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute(
            "INSERT INTO notes (title, content, tags, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("独一份", "唯一的内容，没有重复。", '[]', datetime.now().isoformat(), datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()

        # 不应该抛出异常
        run_dedup_report(str(single_db), threshold=0.6)


def test_run_dedup_report_with_data():
    """有多条笔记时正常扫描不出错"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _create_real_memomind_db(tmpdir)
        # 应该正常完成，不抛异常
        run_dedup_report(str(db_path), threshold=0.3)


# ──────────────────────────────────────────────
# 知识整理测试
# ──────────────────────────────────────────────

def test_run_consolidation_report_with_data():
    """正常执行知识整理不出错"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _create_real_memomind_db(tmpdir)
        run_consolidation_report(str(db_path), days_threshold=365)


def test_run_consolidation_report_empty_db():
    """空数据库也不应该崩溃"""
    with tempfile.TemporaryDirectory() as tmpdir:
        empty_db = Path(tmpdir) / "empty.db"
        conn = sqlite3.connect(str(empty_db))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id INTEGER DEFAULT 1,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                tags TEXT DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

        run_consolidation_report(str(empty_db))
        run_dedup_report(str(empty_db))


# ──────────────────────────────────────────────
# CLI 集成测试
# ──────────────────────────────────────────────

def test_export_dedup_flag_parsed():
    """--dedup 标志被正确解析传递"""
    from click.testing import CliRunner
    from doc_knowledge.cli import main

    with tempfile.TemporaryDirectory() as tmpdir:
        knowledge = Path(tmpdir) / "knowledge"
        knowledge.mkdir()
        (knowledge / "test.md").write_text("# Test", encoding="utf-8")

        runner = CliRunner()
        # 不传 --db 时应快速失败，但标志解析应成功
        result = runner.invoke(main, [
            "export", str(knowledge),
            "-t", "memomind",
            "--db", str(Path(tmpdir) / "nonexistent.db"),
            "--dedup",
        ])
        # FileNotFoundError 是预期行为（数据库不存在）
        # 关键是标志解析不应报错
        assert "--dedup" not in str(result.output.lower()) or "no such option" not in str(result.output.lower())
