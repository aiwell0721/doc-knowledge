"""
语义去重器

使用 TF-IDF + 余弦相似度检测重复文档。
"""

import math
import re
from collections import Counter
from pathlib import Path
from typing import Optional

from doc_knowledge.extractors._pairwise import greedy_dedup


class Deduplicator:
    """语义去重器"""

    def __init__(self, threshold: float = 0.85):
        self.threshold = threshold

    def deduplicate(self, documents: list[dict]) -> tuple[list[dict], list[dict]]:
        if len(documents) <= 1:
            return documents, []

        tfidf_vectors = self._compute_tfidf(documents)
        # 范数只算一次：旧实现在每对比较中重复开方，O(n²) 次 → O(n) 次
        norms = [math.sqrt(sum(v * v for v in vec.values())) for vec in tfidf_vectors]

        def is_similar(i: int, j: int) -> bool:
            return self._cosine_similarity(
                tfidf_vectors[i], tfidf_vectors[j], norms[i], norms[j]
            ) >= self.threshold

        return greedy_dedup(documents, is_similar)

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

    @staticmethod
    def _cosine_similarity(vec1: dict[str, float], vec2: dict[str, float],
                           norm1: float, norm2: float) -> float:
        """余弦相似度（范数预计算传入）

        点积只遍历较小的向量：旧实现先取两向量键并集再逐项 get，
        对稀疏 TF-IDF 向量是近一倍的无效遍历。
        """
        if norm1 == 0 or norm2 == 0:
            return 0.0
        if len(vec1) > len(vec2):
            vec1, vec2 = vec2, vec1
        dot = sum(v * vec2.get(k, 0.0) for k, v in vec1.items())
        return dot / (norm1 * norm2)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        english_words = re.findall(r'[a-zA-Z]{2,}', text.lower())
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
        ngrams = []
        for i in range(len(chinese_chars) - 1):
            ngrams.append(chinese_chars[i] + chinese_chars[i + 1])
        return english_words + ngrams
