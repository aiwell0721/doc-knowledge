"""
SimHash 去重器

用于大规模文档去重（10K+ 文件），O(n) 时间复杂度。
"""

import hashlib
from pathlib import Path


class SimHashDeduplicator:
    """SimHash 大规模去重器"""
    
    def __init__(self, bits: int = 64, threshold: int = 3):
        self.bits = bits
        self.threshold = threshold
    
    def deduplicate(self, documents: list[dict]) -> tuple[list[dict], list[dict]]:
        if len(documents) <= 1:
            return documents, []
        
        hashes = []
        for doc in documents:
            simhash = self._compute_simhash(doc["content"])
            hashes.append(simhash)
        
        is_duplicate = set()
        duplicates = []
        
        for i in range(len(documents)):
            if i in is_duplicate:
                continue
            for j in range(i + 1, len(documents)):
                if j in is_duplicate:
                    continue
                
                distance = self._hamming_distance(hashes[i], hashes[j])
                if distance <= self.threshold:
                    score_i = documents[i].get("score", 0)
                    score_j = documents[j].get("score", 0)
                    
                    if score_i >= score_j:
                        loser = j
                    else:
                        loser = i
                    
                    if loser not in is_duplicate:
                        is_duplicate.add(loser)
                        dup_doc = documents[loser].copy()
                        dup_doc["similar_to"] = documents[i if loser == j else j]["path"]
                        duplicates.append(dup_doc)
                    
                    if loser == i:
                        break
        
        kept = [d for idx, d in enumerate(documents) if idx not in is_duplicate]
        return kept, duplicates
    
    def _compute_simhash(self, text: str) -> int:
        import re
        tokens = re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z]{2,}', text.lower())
        
        v = [0] * self.bits
        for token in tokens:
            h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
            for i in range(self.bits):
                if h & (1 << i):
                    v[i] += 1
                else:
                    v[i] -= 1
        
        fingerprint = 0
        for i in range(self.bits):
            if v[i] > 0:
                fingerprint |= (1 << i)
        
        return fingerprint
    
    @staticmethod
    def _hamming_distance(h1: int, h2: int) -> int:
        xor = h1 ^ h2
        return bin(xor).count("1")
