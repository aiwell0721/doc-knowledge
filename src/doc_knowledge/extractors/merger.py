"""
版本合并器

将同一文档的多个版本合并为最优版本。
"""

import re
from pathlib import Path


class VersionMerger:
    """版本合并器"""
    
    VERSION_PATTERNS = [
        r'_v(\d+)', r'[_\-]v(\d+)[\.\-_]', r'_ver(\d+)',
        r'_version(\d+)', r'(\d+)\.(\d+)', r'[_\-](\d{8})',
        r'_final', r'_latest',
    ]
    
    def merge(self, documents: list[dict]) -> tuple[list[dict], list[dict]]:
        if len(documents) <= 1:
            return documents, []
        
        groups = {}
        for doc in documents:
            base_name = self._strip_version(doc["path"].name)
            if base_name not in groups:
                groups[base_name] = []
            groups[base_name].append(doc)
        
        kept = []
        merged = []
        
        for base_name, docs in groups.items():
            if len(docs) == 1:
                kept.append(docs[0])
                continue
            
            best = self._select_best(docs)
            kept.append(best)
            
            for doc in docs:
                if doc["path"] != best["path"]:
                    merged_doc = doc.copy()
                    merged_doc["merged_into"] = best["path"]
                    merged.append(merged_doc)
        
        return kept, merged
    
    def _select_best(self, docs: list[dict]) -> dict:
        def score(d):
            doc_score = d.get("score", 0)
            content_len = len(d.get("content", ""))
            try:
                mtime = d["path"].stat().st_mtime
            except OSError:
                mtime = 0
            return (doc_score, content_len, mtime)
        
        return max(docs, key=score)
    
    def _strip_version(self, filename: str) -> str:
        name = filename
        base, ext = str(Path(name).stem), name.rsplit(".", 1)[-1] if "." in name else name
        
        for pattern in self.VERSION_PATTERNS:
            base = re.sub(pattern, "", base, flags=re.IGNORECASE)
        
        base = re.sub(r'[_\-]{2,}', '_', base).strip("_-")
        return f"{base}.{ext}"
