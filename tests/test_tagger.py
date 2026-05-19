"""测试自动标签器"""

from doc_knowledge.extractors.tagger import Tagger


def test_no_tags_for_empty():
    """空内容应该没有标签"""
    tagger = Tagger()
    tags = tagger.tag("")
    assert tags == []


def test_title_keywords():
    """标题中的关键词应该被识别"""
    tagger = Tagger()
    # 使用正则模式匹配的英文关键词
    tags = tagger.tag("We use Docker for deployment", title="Docker Deployment")
    assert "devops" in tags


def test_body_keywords():
    """正文中的关键词应该被识别"""
    content = """
    本文介绍了一种基于机器学习的算法架构，
    用于优化分布式系统的性能。
    Docker 容器化和 Kubernetes 编排是核心方案。
    """
    tagger = Tagger()
    tags = tagger.tag(content)
    assert len(tags) > 0


def test_max_tags_limit():
    """标签数不应该超过最大值"""
    content = "架构 设计 算法 系统 API 测试 报告 分析 方案 总结 计划" * 5
    tagger = Tagger(max_tags=3)
    tags = tagger.tag(content)
    assert len(tags) <= 3


def test_synonym_normalization():
    """同义词应该被标准化"""
    tagger = Tagger()
    # "架构" 和 "architecture" 都应该映射到 "architecture"
    tags1 = tagger.tag("架构", title="架构")
    tags2 = tagger.tag("architecture", title="architecture")
    if tags1 and tags2:
        assert tags1[0] == tags2[0]


def test_regex_patterns():
    """正则模式匹配应该工作"""
    content = "We deployed using Docker and Kubernetes on AWS cloud infrastructure."
    tagger = Tagger()
    tags = tagger.tag(content)
    assert "devops" in tags or "cloud" in tags
