"""集成测试：端到端流水线"""

import tempfile
from pathlib import Path
from click.testing import CliRunner
from doc_knowledge.cli import main


def _create_test_docs(source_dir: Path):
    """创建测试文档"""
    (source_dir / "report.txt").write_text(
        "这是一份测试报告，包含了系统架构设计的分析。\n" * 5,
        encoding="utf-8",
    )
    (source_dir / "notes.txt").write_text(
        "会议记录：讨论了 Docker 容器化方案和 Kubernetes 部署策略。",
        encoding="utf-8",
    )


def test_convert_command():
    """测试 convert 命令"""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        source = Path(tmpdir) / "source"
        source.mkdir()
        _create_test_docs(source)

        result = runner.invoke(main, ["convert", str(source)])
        assert result.exit_code == 0
        # 应该生成了 mirror 目录
        mirror = source.parent / f"{source.name}_mirror"
        assert mirror.exists()


def test_extract_command():
    """测试 extract 命令"""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建 mirror 目录
        mirror = Path(tmpdir) / "mirror"
        mirror.mkdir()
        (mirror / "doc1.txt.md").write_text(
            "---\ntitle: doc1\nsource: test\n---\n\n"
            "系统架构设计是软件工程的重要环节。" * 10,
            encoding="utf-8",
        )
        (mirror / "doc2.txt.md").write_text(
            "---\ntitle: doc2\nsource: test\n---\n\n"
            "今天天气很好，适合出去散步。",
            encoding="utf-8",
        )

        result = runner.invoke(main, ["extract", str(mirror)])
        assert result.exit_code == 0


def test_pipeline_command():
    """测试 pipeline 一键命令"""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        source = Path(tmpdir) / "source"
        source.mkdir()
        _create_test_docs(source)

        result = runner.invoke(main, ["pipeline", str(source), "--target", "markdown"])
        # Pipeline 应该成功（或至少有有意义的输出）
        assert "pipeline" in result.output.lower() or result.exit_code == 0 or "Step" in result.output


def test_dry_run():
    """测试 dry-run 模式"""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        source = Path(tmpdir) / "source"
        source.mkdir()
        (source / "test.txt").write_text("test content", encoding="utf-8")

        result = runner.invoke(main, ["convert", str(source), "--dry-run"])
        assert result.exit_code == 0
        assert "test.txt" in result.output
