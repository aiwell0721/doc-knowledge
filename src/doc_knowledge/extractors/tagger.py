"""
自动标签器

基于关键词提取和同义词映射，为文档自动打标签。
"""

import re
from collections import Counter

SYNONYM_MAP = {
    "架构": "architecture", "architecture": "architecture",
    "design": "design", "设计": "design",
    "algorithm": "algorithm", "算法": "algorithm",
    "api": "api", "接口": "api",
    "system": "system", "系统": "system",
    "database": "database", "数据库": "database",
    "测试": "testing", "test": "testing",
    "report": "report", "报告": "report",
    "分析": "analysis", "analysis": "analysis",
    "plan": "planning", "计划": "planning",
    "方案": "solution", "总结": "summary", "summary": "summary",
    "prd": "product", "产品": "product",
    "需求": "requirements", "requirement": "requirements",
    "user": "user_experience", "用户": "user_experience", "体验": "user_experience",
    "文档": "documentation", "doc": "documentation", "manual": "documentation",
    "指南": "guide", "guide": "guide", "tutorial": "tutorial", "教程": "tutorial",
}

KEYWORD_TAGS = [
    (r'[Dd]ocker|[Cc]ontainer', "devops"),
    (r'[Kk]ubernetes|[Kk]8s', "devops"),
    (r'[Cc]loud|[Aa]ws|[Aa]zure', "cloud"),
    (r'[Pp]ython', "python"),
    (r'[Jj]ava', "java"),
    (r'[Jj]ava[Ss]cript|[Tt]ype[Ss]cript|[Rr]eact|[Vv]ue', "frontend"),
    (r'[Mm]achine [Ll]earning|[Aa]rtificial [Ii]ntelligence|[Aa]I', "ai_ml"),
    (r'[Ss]ecurity|[Cc]ryptography', "security"),
    (r'[Pp]erformance|[Oo]ptimiz', "performance"),
    (r'[Dd]ata|[Aa]nalytic', "data"),
    (r'[Mm]icroservice|[Dd]istributed', "distributed_systems"),
    (r'[Ff]inance|[Ff]inancial', "finance"),
    (r'[Mm]arket|[Cc]ompetitor', "business"),
]


class Tagger:
    """自动标签器"""
    
    def __init__(self, max_tags: int = 5):
        self.max_tags = max_tags
    
    def tag(self, content: str, title: str = "") -> list[str]:
        tag_scores: Counter = Counter()
        
        if title:
            title_words = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', title)
            for word in title_words:
                tag = SYNONYM_MAP.get(word.lower(), SYNONYM_MAP.get(word))
                if tag:
                    tag_scores[tag] += 3
        
        words = re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z]{2,}', content.lower())
        word_freq = Counter(words)
        for word, count in word_freq.items():
            tag = SYNONYM_MAP.get(word)
            if tag:
                tag_scores[tag] += count
        
        for pattern, tag in KEYWORD_TAGS:
            matches = len(re.findall(pattern, content))
            if matches > 0:
                tag_scores[tag] += min(matches, 5)
        
        tags = [tag for tag, _score in tag_scores.most_common(self.max_tags)]
        return tags
