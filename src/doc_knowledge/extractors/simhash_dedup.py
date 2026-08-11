"""
SimHash 去重器

用于大规模文档去重（10K+ 文件）。

时间复杂度说明：SimHash 计算 O(n)，但朴素的两两比较是 O(n²)。
threshold 较小（默认 3，≤7）时启用 LSH 分带预筛——n_bands = threshold + 1
个分带，汉明距离 ≤ threshold 的两哈希至少有一个分带完全相同（抽屉原理），
只需比较同带候选对，比较次数从 O(n²) 降为近 O(n)；threshold 较大时
分带失效，自动退回全量两两比较（每对比较为 O(1) 的位运算）。
"""

import hashlib
import re
from pathlib import Path

from doc_knowledge.extractors._pairwise import greedy_dedup


class SimHashDeduplicator:
    """SimHash 大规模去重器"""

    def __init__(self, bits: int = 64, threshold: int = 3):
        self.bits = bits
        self.threshold = threshold

    def deduplicate(self, documents: list[dict]) -> tuple[list[dict], list[dict]]:
        if len(documents) <= 1:
            return documents, []

        hashes = [self._compute_simhash(doc["content"]) for doc in documents]
        candidates = self._build_candidates(hashes)

        def is_similar(i: int, j: int) -> bool:
            return (hashes[i] ^ hashes[j]).bit_count() <= self.threshold

        return greedy_dedup(documents, is_similar, candidates)

    def _build_candidates(self, hashes: list[int]) -> dict[int, set[int]] | None:
        """LSH 分带预筛候选对 {i: {j, ...}}（i < j）；分带无效时返回 None

        分带数 n_bands = threshold + 1：距离 ≤ threshold 的不同位分散到
        n_bands 个带中，至少一个带完全相同，故真重复对必然成为候选。
        要求每带 ≥ 8 位（桶数 ≥ 256），否则碰撞过多、预筛失去意义。
        """
        n_bands = self.threshold + 1
        band_bits = self.bits // n_bands if n_bands >= 2 else 0
        if n_bands < 2 or band_bits < 8:
            return None

        band_mask = (1 << band_bits) - 1
        candidates: dict[int, set[int]] = {}
        for band in range(n_bands):
            shift = band * band_bits
            buckets: dict[int, list[int]] = {}
            for idx, h in enumerate(hashes):
                key = (h >> shift) & band_mask
                buckets.setdefault(key, []).append(idx)
            for bucket in buckets.values():
                for a in range(len(bucket)):
                    for b in range(a + 1, len(bucket)):
                        candidates.setdefault(bucket[a], set()).add(bucket[b])
        return candidates

    def _compute_simhash(self, text: str) -> int:
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
        return (h1 ^ h2).bit_count()
