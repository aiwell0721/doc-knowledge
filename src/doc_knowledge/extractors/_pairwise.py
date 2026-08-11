"""贪心逐对去重主循环（Deduplicator / SimHashDeduplicator 共用）

此前两个去重器各自复制了同一套双重循环，已收敛到此模块。
"""

from typing import Callable, Optional


def greedy_dedup(
    documents: list[dict],
    is_similar: Callable[[int, int], bool],
    candidates: Optional[dict[int, set[int]]] = None,
) -> tuple[list[dict], list[dict]]:
    """贪心逐对去重：相似对中保留 score 较高者（平分保留前者）

    Args:
        documents: 文档列表，每项至少含 "path"，可选 "score"
        is_similar(i, j): 判断 documents[i] 与 documents[j] 是否重复
        candidates: 可选的候选对预筛 {i: {j, ...}}（i < j），
            如 SimHash 的 LSH 分带结果；None 表示全量两两比较。
            预筛必须保证不漏真重复对（分带基于抽屉原理），
            候选对仍需经 is_similar 复核，结果与全量比较一致。

    Returns:
        (保留的文档列表, 去重淘汰的文档列表[含 similar_to])
    """
    n = len(documents)
    if n <= 1:
        return documents, []

    is_duplicate: set[int] = set()
    duplicates: list[dict] = []

    for i in range(n):
        if i in is_duplicate:
            continue
        # 候选预筛时仅遍历候选 j（升序），与全量循环的比较顺序一致，
        # 保证链式相似（A~B、B~C、A!~C）场景下结果与旧实现相同
        js = range(i + 1, n) if candidates is None else sorted(candidates.get(i, ()))
        for j in js:
            if j in is_duplicate:
                continue
            if not is_similar(i, j):
                continue

            score_i = documents[i].get("score", 0)
            score_j = documents[j].get("score", 0)
            loser = j if score_i >= score_j else i

            if loser not in is_duplicate:
                is_duplicate.add(loser)
                dup_doc = documents[loser].copy()
                dup_doc["similar_to"] = documents[i if loser == j else j]["path"]
                duplicates.append(dup_doc)

            if loser == i:
                break

    kept = [d for idx, d in enumerate(documents) if idx not in is_duplicate]
    return kept, duplicates
