"""
MemoMind 导出器

通过 HTTP API 或 MCP 协议将知识文档导出到 MemoMind。
"""

import json
import sqlite3
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional


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
                title, body, tags = self._parse_content(content, md_file)
                self._create_note(title, body, tags)
                stats["exported"] += 1
            except Exception as e:
                stats["errors"] += 1
                stats["error_details"].append(f"{md_file.name}: {e}")
        
        return stats
    
    def _parse_content(self, content: str, filepath: Path) -> tuple[str, str, list[str]]:
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
        cursor = conn.cursor()
        workspace_id = self._get_or_create_workspace(cursor, self.workspace)
        
        try:
            for md_file in sorted(knowledge_dir.rglob("*.md")):
                if md_file.is_dir():
                    continue
                try:
                    content = md_file.read_text(encoding="utf-8")
                    title, body, tags = self._parse_content(content, md_file)
                    
                    now = int(time.time())
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
        cursor.execute("INSERT INTO workspaces (name, created_at) VALUES (?, ?)", (name, int(time.time())))
        return cursor.lastrowid
    
    def _get_or_create_tag(self, cursor, name: str) -> int:
        cursor.execute("SELECT id FROM tags WHERE name = ?", (name,))
        row = cursor.fetchone()
        if row:
            return row[0]
        cursor.execute("INSERT INTO tags (name) VALUES (?)", (name,))
        return cursor.lastrowid
    
    @staticmethod
    def _parse_content(content: str, filepath: Path) -> tuple[str, str, list[str]]:
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
