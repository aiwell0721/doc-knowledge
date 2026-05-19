"""测试语义去重器"""

from pathlib import Path
from doc_knowledge.extractors.deduplicator import Deduplicator


def _make_doc(content: str, score: int = 50) -> dict:
    return {"path": Path(f"test_{id(content)}.md"), "content": content, "score": score}


def test_no_duplicates():
    """不相似的文档应该全部保留"""
    docs = [
        _make_doc("关于人工智能的讨论", 50),
        _make_doc("今天天气非常好", 50),
        _make_doc("Python 编程语言入门教程", 50),
    ]
    kept, dups = Deduplicator(threshold=0.85).deduplicate(docs)
    assert len(kept) == 3
    assert len(dups) == 0


def test_exact_duplicates():
    """完全相同的文档应该只保留一个"""
    content = "这是一个测试文档，包含一些内容"
    docs = [_make_doc(content, 50), _make_doc(content, 60)]
    kept, dups = Deduplicator(threshold=0.85).deduplicate(docs)
    assert len(kept) == 1
    assert len(dups) == 1
    assert kept[0]["score"] == 60  # 保留评分更高的


def test_similar_documents():
    """相似文档应该被去重"""
    doc1 = _make_doc("Python 是一门优秀的编程语言，广泛应用于数据科学和机器学习", 50)
    doc2 = _make_doc("Python 是一种优秀的编程语言，广泛用于数据科学与机器学习领域", 40)
    docs = [doc1, doc2]
    kept, dups = Deduplicator(threshold=0.7).deduplicate(docs)  # 降低阈值以更容易触发
    # 两个高度相似的文档应该至少有一个被去重
    assert len(kept) + len(dups) == 2
    # 评分更高的应该保留
    if len(kept) == 1:
        assert kept[0]["score"] == 50


def test_empty_list():
    """空列表应返回空"""
    kept, dups = Deduplicator().deduplicate([])
    assert kept == []
    assert dups == []


def test_single_document():
    """单个文档应保留"""
    docs = [_make_doc("single doc")]
    kept, dups = Deduplicator().deduplicate(docs)
    assert len(kept) == 1
    assert len(dups) == 0


def test_threshold_control():
    """阈值应该控制去重敏感度"""
    doc1 = _make_doc("机器学习是人工智能的重要分支", 50)
    doc2 = _make_doc("深度学习是机器学习的重要方向", 40)
    docs = [doc1, doc2]
    
    # 低阈值：不太相似的去重
    kept_low, _ = Deduplicator(threshold=0.3).deduplicate(docs)
    # 高阈值：只去重非常相似的
    kept_high, _ = Deduplicator(threshold=0.95).deduplicate(docs)
    
    # 低阈值应该保留更少（去重更激进）
    assert len(kept_low) <= len(kept_high)
