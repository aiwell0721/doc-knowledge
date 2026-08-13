"""
MemoMind 导出器

通过 HTTP API 或 MCP 协议将知识文档导出到 MemoMind。
"""

import json
import logging
import sqlite3
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class MemoMindSchemaError(Exception):
    """MemoMind 数据库 schema 与导出器硬编码假设不兼容"""


# MCP 本地模式直写所需的表与必需列（MemoMind 升级后可能变更）
_REQUIRED_SCHEMA = {
    "workspaces": {"id", "name", "created_at"},
    "notes": {"id", "workspace_id", "title", "content", "created_at", "updated_at"},
    "tags": {"id", "name"},
    "note_tags": {"note_id", "tag_id"},
}


def _validate_memomind_schema(conn) -> None:
    """校验 MemoMind 数据库 4 表必需列存在，缺失抛 MemoMindSchemaError

    直写第三方 SQLite 前必调：schema 漂移方向不可预知（MemoMind 升级），
    与其静默失败或写入错误数据，不如明确拒绝并提示改用 HTTP 模式。
    """
    cursor = conn.cursor()

    missing_tables = []
    for table in _REQUIRED_SCHEMA:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        if cursor.fetchone() is None:
            missing_tables.append(table)
    if missing_tables:
        raise MemoMindSchemaError(
            f"MemoMind 数据库缺少表: {', '.join(missing_tables)}。"
            "schema 可能已随 MemoMind 变更，请改用 HTTP 模式 (--api-url) 或升级 MemoMind"
        )

    missing_columns = {}
    for table, required_cols in _REQUIRED_SCHEMA.items():
        cursor.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in cursor.fetchall()}
        diff = required_cols - existing
        if diff:
            missing_columns[table] = sorted(diff)
    if missing_columns:
        detail = "; ".join(f"{t} 缺 {', '.join(cols)}" for t, cols in missing_columns.items())
        raise MemoMindSchemaError(
            f"MemoMind 数据库 schema 不兼容: {detail}。"
            "请改用 HTTP 模式 (--api-url) 或升级 MemoMind"
        )


class MemoMindExporter:
    """通过 HTTP API 导出到 MemoMind"""

    def __init__(self, api_url: str, api_key: str = "", workspace: str = "default"):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.workspace = workspace

    def export(self, knowledge_dir: Path) -> dict:
        stats = {"exported": 0, "errors": 0, "error_details": []}

        for md_file in sorted(knowledge_dir.rglob("*.md")):
            if md_file.is_dir():
                continue
            try:
                content = md_file.read_text(encoding="utf-8")
                title, body, tags = _parse_frontmatter(content, md_file)
                self._create_note(title, body, tags)
                stats["exported"] += 1
            except Exception as e:
                stats["errors"] += 1
                stats["error_details"].append(f"{md_file.name}: {e}")

        return stats
    
    def _create_note(self, title: str, content: str, tags: list[str]) -> dict:
        url = f"{self.api_url}/api/notes"
        payload = {"title": title, "content": content, "tags": tags, "workspace": self.workspace}
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST",
            headers={"Content-Type": "application/json"})
        if self.api_key:
            req.add_header("Authorization", f"Bearer {self.api_key}")
        
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise ConnectionError(f"无法连接 MemoMind API ({self.api_url}): {e}")


class MemoMindMCPExporter:
    """通过直接写 SQLite 导出到 MemoMind"""

    def __init__(self, memomind_db: Path, workspace: str = "default"):
        self.db_path = memomind_db
        self.workspace = workspace

    def export(self, knowledge_dir: Path) -> dict:
        stats = {"exported": 0, "errors": 0, "error_details": []}

        if not self.db_path.exists():
            raise FileNotFoundError(f"MemoMind 数据库不存在: {self.db_path}")

        conn = sqlite3.connect(str(self.db_path))
        try:
            # 写前校验：schema 不兼容时明确失败，不写坏第三方数据库
            _validate_memomind_schema(conn)
            logger.warning(
                "直写 MemoMind 数据库 %s，建议先备份（schema 可能随 MemoMind 升级变更）",
                self.db_path,
            )

            cursor = conn.cursor()
            workspace_id = self._get_or_create_workspace(cursor, self.workspace)

            for md_file in sorted(knowledge_dir.rglob("*.md")):
                if md_file.is_dir():
                    continue
                try:
                    content = md_file.read_text(encoding="utf-8")
                    title, body, tags = _parse_frontmatter(content, md_file)

                    now = datetime.now(timezone.utc).isoformat()
                    cursor.execute(
                        "INSERT INTO notes (workspace_id, title, content, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                        (workspace_id, title, body, now, now))
                    note_id = cursor.lastrowid

                    for tag in tags:
                        tag_id = self._get_or_create_tag(cursor, tag)
                        cursor.execute("INSERT OR IGNORE INTO note_tags (note_id, tag_id) VALUES (?, ?)",
                            (note_id, tag_id))

                    stats["exported"] += 1
                except Exception as e:
                    stats["errors"] += 1
                    stats["error_details"].append(f"{md_file.name}: {e}")

            conn.commit()
        finally:
            conn.close()

        return stats

    def _get_or_create_workspace(self, cursor, name: str) -> int:
        cursor.execute("SELECT id FROM workspaces WHERE name = ?", (name,))
        row = cursor.fetchone()
        if row:
            return row[0]
        cursor.execute("INSERT INTO workspaces (name, created_at) VALUES (?, ?)", (name, datetime.now(timezone.utc).isoformat()))
        return cursor.lastrowid

    def _get_or_create_tag(self, cursor, name: str) -> int:
        cursor.execute("SELECT id FROM tags WHERE name = ?", (name,))
        row = cursor.fetchone()
        if row:
            return row[0]
        cursor.execute("INSERT INTO tags (name) VALUES (?)", (name,))
        return cursor.lastrowid


def _parse_frontmatter(content: str, filepath: Path) -> tuple[str, str, list[str]]:
    """从 Markdown 文件中提取 title、body 和 tags"""
    import re
    title = filepath.stem
    body = content
    tags = []

    fm_match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
    if fm_match:
        fm_text = fm_match.group(1)
        body = content[fm_match.end():]

        title_match = re.search(r'^title:\s*"(.+?)"', fm_text, re.MULTILINE)
        if title_match:
            title = title_match.group(1)

        tags_match = re.search(r'^dk_tags:\s*\[(.*?)\]', fm_text, re.MULTILINE)
        if tags_match:
            tags_str = tags_match.group(1)
            tags = [t.strip().strip('"') for t in tags_str.split(",") if t.strip()]

    return title, body.strip(), tags
