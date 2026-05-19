"""
Obsidian 导出器
"""

import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional


class ObsidianExporter:
    """导出到 Obsidian Vault"""
    
    def __init__(self, vault_path: Path):
        self.vault_path = vault_path.resolve()
    
    def export(self, knowledge_dir: Path, output_subdir: str = "doc-knowledge") -> dict:
        output_path = self.vault_path / output_subdir
        output_path.mkdir(parents=True, exist_ok=True)
        
        stats = {"exported": 0, "errors": 0, "error_details": []}
        
        for md_file in sorted(knowledge_dir.rglob("*.md")):
            if md_file.is_dir():
                continue
            try:
                content = md_file.read_text(encoding="utf-8")
                rel_path = md_file.relative_to(knowledge_dir)
                updated_content = self._update_frontmatter(content, md_file, rel_path)
                dest = output_path / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(updated_content, encoding="utf-8")
                stats["exported"] += 1
            except Exception as e:
                stats["errors"] += 1
                stats["error_details"].append(f"{md_file.name}: {e}")
        
        return stats
    
    def _update_frontmatter(self, content: str, source_file: Path, rel_path: Path) -> str:
        import re
        fm_match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
        if not fm_match:
            now = datetime.now().strftime("%Y-%m-%d")
            frontmatter = f"---\ntitle: \"{source_file.stem}\"\ncreated: \"{now}\"\ntags: []\n---\n\n"
            return frontmatter + content
        
        fm_content = fm_match.group(1)
        rest = content[fm_match.end():]
        
        if "tags:" not in fm_content:
            fm_content += "\ntags: []"
        if "created:" not in fm_content:
            now = datetime.now().strftime("%Y-%m-%d")
            fm_content += f'\ncreated: "{now}"'
        
        return f"---\n{fm_content}\n---\n\n{rest}"


class MarkdownExporter:
    """导出为标准 Markdown 文件"""
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir.resolve()
    
    def export(self, knowledge_dir: Path) -> dict:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        stats = {"exported": 0, "errors": 0, "error_details": []}
        
        for md_file in sorted(knowledge_dir.rglob("*.md")):
            if md_file.is_dir():
                continue
            try:
                rel_path = md_file.relative_to(knowledge_dir)
                dest = self.output_dir / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(md_file, dest)
                stats["exported"] += 1
            except Exception as e:
                stats["errors"] += 1
                stats["error_details"].append(f"{md_file.name}: {e}")
        
        return stats
