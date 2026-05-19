"""测试价值评分器"""

import tempfile
from pathlib import Path
from doc_knowledge.extractors.scorer import ValueScorer


def test_empty_content():
    """空内容应该得低分"""
    scorer = ValueScorer()
    result = scorer.score("")
    assert result["total"] < 20
    assert not result["passed"]


def test_short_content():
    """很短的内容应该得分较低"""
    scorer = ValueScorer()
    result = scorer.score("test")
    assert result["total"] < 50


def test_structured_content():
    """有标题、列表、代码块的结构化文档应该得分高"""
    content = """# 系统架构设计

## 概述

本文档描述了系统的整体架构。

## 核心模块

- 转换器模块
- 提取器模块
- 导出器模块

## API 设计

```python
def convert(filepath):
    pass
```

## 性能指标

| 指标 | 值 |
|------|-----|
| 延迟 | 10ms |
| 吞吐 | 1000/s |
"""
    scorer = ValueScorer()
    result = scorer.score(content)
    assert result["structure"] > 50
    assert result["passed"]


def test_min_score_filter():
    """最低分数过滤应该生效"""
    scorer = ValueScorer(min_score=50)
    result = scorer.score("short")
    assert not result["passed"]


def test_freshness_with_file():
    """新鲜度评分应该基于文件修改时间"""
    scorer = ValueScorer()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("test content " * 100)
        f.flush()
        filepath = Path(f.name)
    result = scorer.score("test content " * 100, filepath)
    # 刚创建的文件应该获得较高的新鲜度分
    assert result["freshness"] > 80


def test_keyword_detection():
    """关键词检测应该工作"""
    content = "本文讨论了系统架构设计和算法优化的方案。" * 10
    scorer = ValueScorer()
    result = scorer.score(content)
    assert result["keywords"] > 0
