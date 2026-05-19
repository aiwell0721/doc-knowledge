"""
Doc-Knowledge 提取器模块

语义去重、价值评分、自动标签、版本合并。
"""

from .deduplicator import Deduplicator
from .scorer import ValueScorer
from .tagger import Tagger
from .merger import VersionMerger
from .simhash_dedup import SimHashDeduplicator

__all__ = ["Deduplicator", "ValueScorer", "Tagger", "VersionMerger", "SimHashDeduplicator"]
