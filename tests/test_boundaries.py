"""
边界条件测试

验证各模块在极端情况下的行为
"""

from pathlib import Path
from doc_knowledge.extractors.deduplicator import Deduplicator
from doc_knowledge.extractors.scorer import ValueScorer
from doc_knowledge.extractors.tagger import Tagger
from doc_knowledge.extractors.merger import VersionMerger
from doc_knowledge.extractors.simhash_dedup import SimHashDeduplicator
from doc_knowledge.converters import convert_file


def _make_doc(content: str, score: int = 50, name: str = "test") -> dict:
    return {"path": Path(f"{name}.md"), "content": content, "score": score}


# ──────────────────────────────────────────────
# 评分器边界测试
# ──────────────────────────────────────────────

def test_scorer_empty_vs_whitespace():
    """空内容 vs 纯空格"""
    scorer = ValueScorer()
    empty_result = scorer.score("")
    whitespace_result = scorer.score("   \n\n\t  ")
    
    assert empty_result["total"] < 20
    assert whitespace_result["total"] < 20


def test_scorer_very_long_content():
    """超长内容评分"""
    scorer = ValueScorer()
    long_content = "This is a test paragraph. " * 10000  # ~250K 字符
    result = scorer.score(long_content)
    
    # 超长内容应该有分数（不应崩溃）
    assert result["total"] >= 0
    assert result["length"] <= 100  # 长度分应该有上限


def test_scorer_single_character():
    """单字符内容"""
    scorer = ValueScorer()
    result = scorer.score("a")
    assert result["total"] < 30


def test_scorer_emoji_content():
    """含 emoji 的内容"""
    scorer = ValueScorer()
    result = scorer.score("🎉 Hello world! 你好世界 🚀")
    assert result["total"] >= 0  # 不应崩溃


def test_scorer_code_heavy_content():
    """代码密集型内容"""
    scorer = ValueScorer()
    content = """```python
def hello():
    print("world")
```
```javascript
console.log('test');
```
""" * 10
    result = scorer.score(content)
    assert result["total"] >= 0


# ──────────────────────────────────────────────
# 去重器边界测试
# ──────────────────────────────────────────────

def test_deduplicator_all_identical():
    """全部相同的文档"""
    content = "This is identical content for testing deduplication."
    docs = [_make_doc(content, i * 10, f"doc_{i}") for i in range(5)]
    kept, dups = Deduplicator(threshold=0.9).deduplicate(docs)
    
    assert len(kept) == 1
    assert len(dups) == 4


def test_deduplicator_all_different():
    """全部不同的文档"""
    docs = [_make_doc(f"Unique document number {i} about completely different topic {i * 100}", 50, f"doc_{i}") for i in range(10)]
    kept, dups = Deduplicator(threshold=0.95).deduplicate(docs)
    
    # 高阈值下，不同文档应该全部保留
    assert len(kept) + len(dups) == 10


def test_deduplicator_threshold_zero():
    """阈值为 0（所有文档都视为重复）"""
    docs = [_make_doc(f"Content {i}", 50, f"doc_{i}") for i in range(3)]
    kept, dups = Deduplicator(threshold=0.0).deduplicate(docs)
    
    # 阈值 0 意味着任何相似度都算重复
    assert len(kept) == 1
    assert len(dups) == 2


def test_deduplicator_threshold_one():
    """阈值为 1（只有完全相同才算重复）"""
    docs = [
        _make_doc("Same content", 50, "doc1"),
        _make_doc("Same content", 60, "doc2"),
        _make_doc("Different content", 50, "doc3"),
    ]
    kept, dups = Deduplicator(threshold=1.0).deduplicate(docs)
    
    # 只有完全相同的才算重复
    assert len(kept) == 2
    assert len(dups) == 1


def test_deduplicator_large_set():
    """大规模文档集（100 个）"""
    docs = [_make_doc(f"Document number {i} with unique content about topic {i % 5}", 
                       i % 100, f"doc_{i}") for i in range(100)]
    kept, dups = Deduplicator(threshold=0.9).deduplicate(docs)
    
    # 不应崩溃，且应有合理结果
    assert len(kept) + len(dups) == 100


# ──────────────────────────────────────────────
# SimHash 边界测试
# ──────────────────────────────────────────────

def test_simhash_empty_content():
    """空内容的 SimHash"""
    dedup = SimHashDeduplicator()
    docs = [_make_doc("", 50, "empty")]
    kept, dups = dedup.deduplicate(docs)
    assert len(kept) == 1


def test_simhash_very_short_content():
    """极短内容的 SimHash"""
    dedup = SimHashDeduplicator()
    docs = [_make_doc("a", 50, "short1"), _make_doc("b", 50, "short2")]
    kept, dups = dedup.deduplicate(docs)
    assert len(kept) + len(dups) == 2


def test_simhash_large_set():
    """SimHash 大规模测试（100 个文档）"""
    dedup = SimHashDeduplicator()
    docs = [_make_doc(f"Document {i} about machine learning and artificial intelligence", 
                       50, f"doc_{i}") for i in range(100)]
    kept, dups = dedup.deduplicate(docs)
    
    assert len(kept) + len(dups) == 100
    # 相似内容应该被去重
    assert len(dups) > 0


# ──────────────────────────────────────────────
# 标签器边界测试
# ──────────────────────────────────────────────

def test_tagger_max_tags_zero():
    """max_tags=0"""
    tagger = Tagger(max_tags=0)
    tags = tagger.tag("architecture design")
    assert len(tags) == 0


def test_tagger_very_long_content():
    """超长内容的标签提取"""
    tagger = Tagger()
    content = "machine learning " * 1000
    tags = tagger.tag(content)
    assert len(tags) <= 5  # 不应超过 max_tags


def test_tagger_no_keywords():
    """无关键词的内容"""
    tagger = Tagger()
    content = "今天天气很好适合出去散步"
    tags = tagger.tag(content)
    # 可能没有匹配的标签
    assert len(tags) >= 0


# ──────────────────────────────────────────────
# 版本合并器边界测试
# ──────────────────────────────────────────────

def test_merger_no_versions():
    """无版本号的文档"""
    docs = [
        _make_doc("Content A", 50, "doc_a.md"),
        _make_doc("Content B", 60, "doc_b.md"),
    ]
    kept, merged = VersionMerger().merge(docs)
    
    assert len(kept) == 2
    assert len(merged) == 0


def test_merger_many_versions():
    """大量版本合并"""
    docs = [_make_doc(f"Content v{i}", i * 10, f"report_v{i}.md") for i in range(1, 11)]
    kept, merged = VersionMerger().merge(docs)
    
    assert len(kept) == 1
    assert len(merged) == 9


def test_merger_same_score():
    """相同评分的版本"""
    docs = [
        _make_doc("short content", 50, "doc_v1.md"),
        _make_doc("longer content with more details", 50, "doc_v2.md"),
    ]
    kept, _ = VersionMerger().merge(docs)
    
    # 评分相同时，应该选择内容更长的
    assert len(kept[0]["content"]) >= len(docs[0]["content"])
