"""
MemoMind 后处理模块

导出完成后调用 MemoMind SDK 的语义服务和知识图谱服务，
输出去重扫描报告和知识整理建议，无需 HTTP API 认证。

使用方式:
    # CLI 集成
    python -m doc_knowledge export ... --dedup --consolidate

    # 独立调用
    from doc_knowledge.exporters.memomind_post import run_dedup_report
    run_dedup_report("/path/to/memomind.db")
"""

from rich.console import Console
from rich.table import Table

console = Console()


def _get_client(db_path: str):
    """延迟导入 MemoMind SDK，未安装时给出友好报错"""
    try:
        from api.client import MemoMind
    except ImportError:
        raise ImportError(
            "MemoMind SDK 未安装，无法运行后处理。\n"
            "安装: pip install memomind>=2.0.0"
        )
    return MemoMind(db_path)


def run_dedup_report(
    db_path: str,
    workspace_name: str = "default",
    threshold: float = 0.6,
) -> None:
    """扫描重复笔记并打印报告

    调用 MemoMind SemanticService.scan_duplicates() 进行
    TF-IDF 语义去重扫描，按相似度降序展示重复笔记组。

    Args:
        db_path: MemoMind SQLite 数据库路径
        workspace_name: 工作区名称（默认 "default"）
        threshold: 余弦相似度阈值（0.0-1.0，默认 0.6）
    """
    client = _get_client(db_path)
    try:
        # 解析工作区 ID（需要 name → id 映射）
        dup_groups = client._semantic.scan_duplicates(threshold=threshold)

        if not dup_groups:
            console.print("[green]✓ 未发现重复笔记[/green]")
            return

        console.print(f"\n[bold]🔍 语义去重扫描报告[/bold]")
        console.print(f"相似度阈值: {threshold}，发现 {len(dup_groups)} 组重复\n")

        table = Table(title=f"重复笔记组（数据库: {db_path}）")
        table.add_column("#", style="dim", width=4)
        table.add_column("相似度", justify="right", style="yellow")
        table.add_column("笔记标题", style="cyan")
        table.add_column("共享标签", style="green")

        for i, group in enumerate(dup_groups, 1):
            notes = group["notes"]
            max_sim = group.get("max_similarity", 0)
            common_tags = group.get("common_tags", [])

            titles = " / ".join(n.title for n in notes[:3])
            if len(notes) > 3:
                titles += f" ... (+{len(notes) - 3})"

            table.add_row(
                str(i),
                f"{max_sim:.1%}",
                titles,
                ", ".join(common_tags[:5]),
            )

        console.print(table)
        console.print(f"\n[dim]共 {len(dup_groups)} 组重复笔记，建议手动审查后合并[/dim]")

    finally:
        client.close()


def run_consolidation_report(
    db_path: str,
    workspace_name: str = "default",
    days_threshold: int = 90,
    similarity_threshold: float = 0.6,
) -> None:
    """运行知识整理建议并打印报告

    调用 MemoMind KnowledgeGraphService.suggest_consolidation() 分析：
    - 主题聚类（自动标签提取 + 笔记分组）
    - 合并建议（Jaccard 高相似度笔记对）
    - 陈旧笔记检测（超过指定天数未更新）

    Args:
        db_path: MemoMind SQLite 数据库路径
        workspace_name: 工作区名称（默认 "default"）
        days_threshold: 陈旧笔记天数阈值（默认 90 天）
        similarity_threshold: Jaccard 相似度阈值（默认 0.6）
    """
    client = _get_client(db_path)
    try:
        result = client._kg.suggest_consolidation(
            days_threshold=days_threshold,
            similarity_threshold=similarity_threshold,
        )

        topics = result.get("topics", [])
        merge_suggestions = result.get("merge_suggestions", [])
        stale_candidates = result.get("stale_candidates", [])

        console.print(f"\n[bold]📊 知识整理建议报告[/bold]\n")

        # 1. 主题聚类
        if topics:
            console.print(f"[bold]📁 主题聚类（{len(topics)} 个主题）[/bold]")
            topic_table = Table()
            topic_table.add_column("主题", style="cyan")
            topic_table.add_column("笔记数", justify="right")
            for topic in topics:
                topic_table.add_row(
                    topic.get("name", "未命名"),
                    str(topic.get("note_count", 0)),
                )
            console.print(topic_table)
        else:
            console.print("[dim]未发现明显主题聚类[/dim]")

        # 2. 合并建议
        if merge_suggestions:
            console.print(f"\n[bold]🔗 合并建议（{len(merge_suggestions)} 组）[/bold]")
            merge_table = Table()
            merge_table.add_column("#", style="dim", width=4)
            merge_table.add_column("笔记对", style="cyan")
            merge_table.add_column("相似度", justify="right", style="yellow")

            for i, suggestion in enumerate(merge_suggestions, 1):
                note_ids = suggestion.get("note_ids", [])
                similarity = suggestion.get("similarity", 0)
                # 尝试获取笔记标题
                titles = []
                for nid in note_ids[:2]:
                    note = client.notes.get(nid)
                    titles.append(note["title"] if note else f"#{nid}")
                merge_table.add_row(str(i), " ↔ ".join(titles), f"{similarity:.1%}")

            console.print(merge_table)
        else:
            console.print("[dim]未发现可合并笔记[/dim]")

        # 3. 陈旧笔记
        if stale_candidates:
            console.print(
                f"\n[bold]⏰ 陈旧笔记（{len(stale_candidates)} 条，>{days_threshold}天未更新）[/bold]"
            )
            stale_table = Table()
            stale_table.add_column("#", style="dim", width=4)
            stale_table.add_column("标题", style="cyan")
            stale_table.add_column("天数", justify="right", style="yellow")

            for i, stale in enumerate(stale_candidates, 1):
                stale_table.add_row(
                    str(i),
                    stale.get("title", "无标题"),
                    str(stale.get("days_since_update", "?")),
                )
            console.print(stale_table)
        else:
            console.print("[dim]未发现陈旧笔记[/dim]")

    finally:
        client.close()
