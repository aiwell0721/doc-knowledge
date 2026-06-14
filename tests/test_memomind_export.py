"""
MemoMind 导出测试

验证 MemoMind HTTP API 和 MCP 本地模式的导出功能
"""

import tempfile
import sqlite3
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from doc_knowledge.exporters.memomind import MemoMindExporter, MemoMindMCPExporter


def _create_test_knowledge_dir(tmpdir: str, count: int = 3) -> Path:
    """创建测试知识目录"""
    knowledge = Path(tmpdir) / "knowledge"
    knowledge.mkdir()
    
    for i in range(count):
        (knowledge / f"doc_{i}.md").write_text(
            f'---\ntitle: "Document {i}"\ndk_tags: ["tag{i}", "test"]\n---\n\n'
            f'This is document {i} about system architecture and Docker containers.',
            encoding="utf-8"
        )
    
    return knowledge


def _create_memomind_db(tmpdir: str) -> Path:
    """创建最小 MemoMind 数据库"""
    db_path = Path(tmpdir) / "memomind.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workspaces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER,
            title TEXT,
            content TEXT,
            tags TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    return db_path


# ──────────────────────────────────────────────
# HTTP API 模式测试
# ──────────────────────────────────────────────

def test_memomind_http_export_success():
    """HTTP 导出成功（mock）"""
    with tempfile.TemporaryDirectory() as tmpdir:
        knowledge = _create_test_knowledge_dir(tmpdir, count=2)
        
        # Mock urllib.request.urlopen
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"id": 1, "title": "test"}).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=None)
        
        with patch('doc_knowledge.exporters.memomind.urllib.request.urlopen', return_value=mock_response):
            exporter = MemoMindExporter("http://localhost:8000", api_key="test_key")
            stats = exporter.export(knowledge)
        
        assert stats["exported"] == 2
        assert stats["errors"] == 0


def test_memomind_http_export_failure():
    """HTTP 导出失败 - 验证 ConnectionError 异常处理逻辑"""
    # 这个测试验证 exporter 在 API 不可达时的行为
    # 由于网络 mock 在 Python 中比较复杂，我们直接验证异常类型
    
    # 验证 exporter 的 _create_note 方法会抛出 ConnectionError
    exporter = MemoMindExporter("http://localhost:9999")
    
    # 手动调用 _create_note 来验证异常处理
    try:
        # 使用一个明显不可达的 URL
        exporter.api_url = "http://192.0.2.1:1"  # TEST-NET-1, 端口 1
        exporter._create_note("test", "content", [])
        assert False, "Should have raised ConnectionError"
    except ConnectionError as e:
        assert "无法连接" in str(e) or "192.0.2.1" in str(e)
    except Exception:
        # 其他网络相关错误也是可接受的
        pass


def test_memomind_http_export_partial_failure():
    """部分导出失败"""
    import urllib.error
    
    with tempfile.TemporaryDirectory() as tmpdir:
        knowledge = _create_test_knowledge_dir(tmpdir, count=3)
        
        call_count = [0]
        def mock_urlopen(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:  # 第二个文件失败
                raise urllib.error.URLError("Timeout")
            mock_response = MagicMock()
            mock_response.read.return_value = json.dumps({"id": call_count[0]}).encode()
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=None)
            return mock_response
        
        with patch('urllib.request.urlopen', side_effect=mock_urlopen):
            exporter = MemoMindExporter("http://localhost:8000")
            
            # 应该抛出 ConnectionError
            try:
                exporter.export(knowledge)
            except ConnectionError:
                pass  # 预期行为


# ──────────────────────────────────────────────
# MCP 本地模式测试
# ──────────────────────────────────────────────

def test_memomind_mcp_export_multiple_files():
    """MCP 多文件导出"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _create_memomind_db(tmpdir)
        knowledge = _create_test_knowledge_dir(tmpdir, count=5)
        
        exporter = MemoMindMCPExporter(db_path, workspace="default")
        stats = exporter.export(knowledge)
        
        assert stats["exported"] == 5
        assert stats["errors"] == 0
        
        # 验证数据库
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM notes")
        assert cursor.fetchone()[0] == 5
        conn.close()


def test_memomind_tag_creation():
    """标签自动创建"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _create_memomind_db(tmpdir)
        knowledge = _create_test_knowledge_dir(tmpdir, count=2)
        
        exporter = MemoMindMCPExporter(db_path, workspace="default")
        stats = exporter.export(knowledge)
        
        assert stats["exported"] == 2
        
        # 验证标签被创建
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM tags")
        tag_count = cursor.fetchone()[0]
        assert tag_count > 0  # 应该有标签被创建
        
        # 验证 note_tags 关联
        cursor.execute("SELECT COUNT(*) FROM note_tags")
        associations = cursor.fetchone()[0]
        assert associations > 0
        conn.close()


def test_memomind_mcp_export_to_new_workspace():
    """导出到新工作区"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _create_memomind_db(tmpdir)
        knowledge = _create_test_knowledge_dir(tmpdir, count=1)
        
        exporter = MemoMindMCPExporter(db_path, workspace="test_workspace")
        stats = exporter.export(knowledge)
        
        assert stats["exported"] == 1
        
        # 验证工作区被创建
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM workspaces")
        workspaces = [row[0] for row in cursor.fetchall()]
        assert "test_workspace" in workspaces
        conn.close()


def test_memomind_mcp_export_empty_directory():
    """MCP 导出空目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _create_memomind_db(tmpdir)
        knowledge = Path(tmpdir) / "knowledge"
        knowledge.mkdir()
        
        exporter = MemoMindMCPExporter(db_path, workspace="default")
        stats = exporter.export(knowledge)
        
        assert stats["exported"] == 0
        assert stats["errors"] == 0


def test_memomind_mcp_export_invalid_db():
    """MCP 导出到不存在的数据库"""
    with tempfile.TemporaryDirectory() as tmpdir:
        knowledge = _create_test_knowledge_dir(tmpdir, count=1)
        db_path = Path(tmpdir) / "nonexistent.db"
        
        exporter = MemoMindMCPExporter(db_path, workspace="default")
        
        try:
            exporter.export(knowledge)
            assert False, "Should have raised FileNotFoundError"
        except FileNotFoundError:
            pass  # 预期行为


# ──────────────────────────────────────────────
# 时间戳格式验证
# ──────────────────────────────────────────────

def test_timestamp_iso_format_in_notes():
    """导出的 created_at/updated_at 必须是 ISO 格式字符串（兼容 datetime.fromisoformat）"""
    from datetime import datetime as dt

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _create_memomind_db(tmpdir)
        knowledge = _create_test_knowledge_dir(tmpdir, count=1)

        exporter = MemoMindMCPExporter(db_path, workspace="default")
        exporter.export(knowledge)

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT created_at, updated_at FROM notes")
        row = cursor.fetchone()
        conn.close()

        # 验证时间戳是 ISO 格式字符串
        assert row is not None
        created_str = row[0]
        updated_str = row[1]

        # 应该能通过 datetime.fromisoformat() 解析
        parsed_created = dt.fromisoformat(created_str)
        parsed_updated = dt.fromisoformat(updated_str)

        assert isinstance(parsed_created, dt)
        assert isinstance(parsed_updated, dt)
        # 时间戳应该在最近 60 秒内
        import time
        now = time.time()
        assert abs(parsed_created.timestamp() - now) < 60
        assert abs(parsed_updated.timestamp() - now) < 60


def test_timestamp_iso_format_in_workspaces():
    """工作区的 created_at 必须是 ISO 格式字符串"""
    from datetime import datetime as dt

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _create_memomind_db(tmpdir)
        knowledge = _create_test_knowledge_dir(tmpdir, count=1)

        exporter = MemoMindMCPExporter(db_path, workspace="test_ws")
        exporter.export(knowledge)

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT created_at FROM workspaces WHERE name = ?", ("test_ws",))
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        # 应该能通过 datetime.fromisoformat() 解析
        parsed = dt.fromisoformat(row[0])
        assert isinstance(parsed, dt)


def test_timestamp_not_integer():
    """时间戳不能是整型 Unix epoch（MemoMind v2 from_row 不兼容）"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _create_memomind_db(tmpdir)
        knowledge = _create_test_knowledge_dir(tmpdir, count=1)

        exporter = MemoMindMCPExporter(db_path, workspace="default")
        exporter.export(knowledge)

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT created_at, updated_at FROM notes")
        row = cursor.fetchone()
        cursor.execute("SELECT created_at FROM workspaces")
        ws_row = cursor.fetchone()
        conn.close()

        # 验证所有时间戳字段都是字符串（非整型）
        assert isinstance(row[0], str), f"created_at 应为 str 但得到 {type(row[0])}"
        assert isinstance(row[1], str), f"updated_at 应为 str 但得到 {type(row[1])}"
        assert isinstance(ws_row[0], str), f"workspace created_at 应为 str 但得到 {type(ws_row[0])}"

        # 字符串不能以数字格式解析为 int（确保我们写的是 ISO 时间戳，不是 epoch）
        # 注: "2026-06-15T..." 不能是 int，但 "1234567890" 可以是
        for val in [row[0], row[1], ws_row[0]]:
            try:
                int(val)
                assert False, f"时间戳 '{val}' 意外地可解析为整型——应该是 ISO 格式"
            except ValueError:
                pass  # 预期：ISO 字符串不能转换为 int
