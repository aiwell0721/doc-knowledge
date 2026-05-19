"""
语义去重器

使用 TF-IDF + 余弦相似度检测重复文档。
"""

import math
from collections import Counter
from pathlib import Path
from typing import Optional


class Deduplicator:
    """语义去重器"""
    
    def __init__(self, threshold: float = 0.85):
        self.threshold = threshold
    
    def deduplicate(self, documents: list[dict]) -> tuple[list[dict], list[dict]]:
        if len(documents) <= 1:
            return documents, []
        
        tfidf_vectors = self._compute_tfidf(documents)
        
        is_duplicate = set()
        duplicates = []
        
        for i in range(len(documents)):
            if i in is_duplicate:
                continue
            for j in range(i + 1, len(documents)):
                if j in is_duplicate:
                    continue
                
                similarity = self._cosine_similarity(tfidf_vectors[i], tfidf_vectors[j])
                if similarity >= self.threshold:
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
    
    def _compute_tfidf(self, documents: list[dict]) -> list[dict[str, float]]:
        n_docs = len(documents)
        
        tokenized = []
        for doc in documents:
            tokens = self._tokenize(doc["content"])
            tokenized.append(tokens)
        
        doc_freq: Counter = Counter()
        for tokens in tokenized:
            unique_tokens = set(tokens)
            for token in unique_tokens:
                doc_freq[token] += 1
        
        vectors = []
        for tokens in tokenized:
            tf = Counter(tokens)
            total = len(tokens) if tokens else 1
            vec: dict[str, float] = {}
            for term, count in tf.items():
                tf_val = count / total
                idf_val = math.log(n_docs / (1 + doc_freq[term]))
                vec[term] = tf_val * idf_val
            vectors.append(vec)
        
        return vectors
    
    def _cosine_similarity(self, vec1: dict[str, float], vec2: dict[str, float]) -> float:
        all_keys = set(vec1.keys()) | set(vec2.keys())
        if not all_keys:
            return 0.0
        
        dot = sum(vec1.get(k, 0) * vec2.get(k, 0) for k in all_keys)
        norm1 = math.sqrt(sum(v * v for v in vec1.values()))
        norm2 = math.sqrt(sum(v * v for v in vec2.values()))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot / (norm1 * norm2)
    
    @staticmethod
    def _tokenize(text: str) -> list[str]:
        import re
        english_words = re.findall(r'[a-zA-Z]{2,}', text.lower())
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
        ngrams = []
        for i in range(len(chinese_chars) - 1):
            ngrams.append(chinese_chars[i] + chinese_chars[i + 1])
        return english_words + ngrams
