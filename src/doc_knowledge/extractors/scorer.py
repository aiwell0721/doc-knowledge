"""
价值评分器

基于 5 因子启发式评分，对文档质量进行打分（0-100）。
"""

import re
import math
from collections import Counter
from pathlib import Path
from datetime import datetime
from typing import Optional


WEIGHTS = {
    "length": 0.20,
    "structure": 0.25,
    "freshness": 0.15,
    "keywords": 0.20,
    "uniqueness": 0.20,
}

KEY_PATTERNS = [
    r'架构', r'设计', r'分析', r'报告', r'方案', r'总结', r'计划',
    r'算法', r'系统', r'模型', r'框架', r'协议', r'规范',
    r'API', r'SDK', r'HTTP', r'JSON', r'XML',
    r'performance', r'architecture', r'algorithm', r'system',
]


class ValueScorer:
    """文档价值评分器"""
    
    def __init__(self, min_score: int = 30, ideal_length: int = 2000):
        self.min_score = min_score
        self.ideal_length = ideal_length
    
    def score(self, content: str, filepath: Optional[Path] = None) -> dict:
        length_score = self._score_length(content)
        structure_score = self._score_structure(content)
        freshness_score = self._score_freshness(filepath)
        keywords_score = self._score_keywords(content)
        uniqueness_score = self._score_uniqueness(content)
        
        total = int(
            length_score * WEIGHTS["length"] +
            structure_score * WEIGHTS["structure"] +
            freshness_score * WEIGHTS["freshness"] +
            keywords_score * WEIGHTS["keywords"] +
            uniqueness_score * WEIGHTS["uniqueness"]
        )
        
        return {
            "total": total,
            "length": round(length_score, 1),
            "structure": round(structure_score, 1),
            "freshness": round(freshness_score, 1),
            "keywords": round(keywords_score, 1),
            "uniqueness": round(uniqueness_score, 1),
            "passed": total >= self.min_score,
        }
    
    def _score_length(self, content: str) -> float:
        length = len(content)
        if length == 0:
            return 0.0
        ratio = min(length / self.ideal_length, 2.0)
        if ratio <= 1.0:
            return ratio * 100
        else:
            return max(0, 100 - (ratio - 1.0) * 50)
    
    def _score_structure(self, content: str) -> float:
        score = 0.0
        headings = re.findall(r'^#{1,6}\s+.+', content, re.MULTILINE)
        if headings:
            score += 30
            if len(headings) >= 3:
                score += 10
        lists = re.findall(r'^[\s]*[-*]\s+.+', content, re.MULTILINE)
        if lists:
            score += 15
        code_blocks = re.findall(r'^```', content, re.MULTILINE)
        if code_blocks:
            score += 10
        tables = re.findall(r'\|', content)
        if len(tables) > 4:
            score += 15
        links = re.findall(r'\[.+?\]\(.+?\)', content)
        if links:
            score += 10
        return min(score, 100.0)
    
    def _score_freshness(self, filepath: Optional[Path]) -> float:
        if filepath is None or not filepath.exists():
            return 50.0
        try:
            mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
            now = datetime.now()
            days_old = (now - mtime).days
            if days_old <= 30:
                return 100.0
            elif days_old <= 180:
                return 100 - (days_old - 30) * 0.3
            elif days_old <= 365:
                return 55 - (days_old - 180) * 0.15
            else:
                return max(10.0, 40 - (days_old - 365) * 0.01)
        except (OSError, ValueError):
            return 50.0
    
    def _score_keywords(self, content: str) -> float:
        if not content:
            return 0.0
        total_words = len(content)
        keyword_count = 0
        for pattern in KEY_PATTERNS:
            keyword_count += len(re.findall(pattern, content, re.IGNORECASE))
        density = keyword_count / max(total_words, 1)
        if density < 0.005:
            return density / 0.005 * 100
        elif density <= 0.03:
            return 100.0
        else:
            return max(50.0, 100 - (density - 0.03) * 2000)
    
    def _score_uniqueness(self, content: str) -> float:
        if not content:
            return 0.0
        char_freq = Counter(content)
        total = len(content)
        entropy = -sum(
            (count / total) * math.log2(count / total)
            for count in char_freq.values() if count > 0
        )
        if entropy < 4:
            return 20.0
        elif entropy < 8:
            return 50.0
        else:
            return min(100.0, 70 + (entropy - 8) * 7.5)
