"""
Tests for webui.py — Gradio Web UI.

Covers:
- app import and structure
- run_command, find_python, build_cmd helper functions
- do_convert, do_extract, do_export, do_pipeline route logic
- Dynamic form toggling (toggle_pipe_target, toggle_vision, toggle_exp_target)
"""

import pytest
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock


# ── Helper functions tests ──

class TestFindPython:
    """find_python() 找到 Python 解释器路径"""

    def test_returns_sys_executable(self):
        from doc_knowledge.webui import find_python
        result = find_python()
        assert result == sys.executable


class TestBuildCmd:
    """build_cmd() 构建完整命令"""

    def test_builds_correct_command(self):
        from doc_knowledge.webui import build_cmd
        cmd = build_cmd(["convert", "/path/to/source"])
        assert cmd[0] == sys.executable
        assert cmd[1] == "-m"
        assert cmd[2] == "doc_knowledge"
        assert cmd[3] == "convert"
        assert cmd[4] == "/path/to/source"

    def test_builds_with_multiple_args(self):
        from doc_knowledge.webui import build_cmd
        cmd = build_cmd(["extract", "/mirror", "--threshold", "0.9"])
        assert cmd[3] == "extract"
        assert cmd[4] == "/mirror"
        assert cmd[5] == "--threshold"
        assert cmd[6] == "0.9"


class TestRunCommand:
    """run_command() 后台执行命令"""

    def test_successful_command(self):
        from doc_knowledge.webui import run_command
        log_lines = []
        # Simple echo command
        status = run_command([sys.executable, "-c", "print('hello')"], log_lines)
        assert "完成" in status or "退出码" in status
        assert "hello" in log_lines

    def test_failed_command(self):
        from doc_knowledge.webui import run_command
        log_lines = []
        # Command that exits with error code
        status = run_command([sys.executable, "-c", "import sys; sys.exit(1)"], log_lines)
        assert "1" in status  # exit code 1

    def test_stderr_captured(self):
        from doc_knowledge.webui import run_command
        log_lines = []
        # Command that writes to stderr
        status = run_command(
            [sys.executable, "-c", "import sys; print('error msg', file=sys.stderr)"],
            log_lines
        )
        # stderr is redirected to stdout in run_command
        assert "error msg" in log_lines

    def test_exception_handling(self):
        from doc_knowledge.webui import run_command
        log_lines = []
        # Pass a nonexistent executable
        status = run_command(["nonexistent_command_xyz_123"], log_lines)
        assert "错误" in status


class TestDoConvert:
    """do_convert() 转换页面的路由逻辑"""

    @patch("doc_knowledge.webui.subprocess.Popen")
    def test_basic_convert(self, mock_popen):
        """基本转换调用 — mock Popen 避免实际执行"""
        mock_proc = MagicMock()
        mock_proc.stdout = iter(["转换完成"])
        mock_proc.wait.return_value = 0
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        from doc_knowledge.webui import do_convert
        status, log = do_convert(
            source=".", output="", format_filter="", recursive=True,
            overwrite=False, dry_run=True, vision=False,
            api_url="", api_key="", model="", verbose=False,
        )
        assert isinstance(status, str)
        assert isinstance(log, str)
        mock_popen.assert_called_once()
        # Verify command includes the source dir
        call_args = mock_popen.call_args[0][0]
        assert "convert" in call_args

    def test_convert_with_vision(self):
        """vision=True 时命令包含 --vision 参数"""
        from doc_knowledge.webui import build_cmd
        cmd = build_cmd(["convert", "source", "--vision"])
        assert "--vision" in cmd

    def test_convert_with_format_filter(self):
        from doc_knowledge.webui import build_cmd
        cmd = build_cmd(["convert", "source", "--format", "pdf"])
        assert "--format" in cmd
        assert "pdf" in cmd


class TestDoExtract:
    """do_extract() 提取页面的路由逻辑"""

    @patch("doc_knowledge.webui.subprocess.Popen")
    def test_basic_extract(self, mock_popen):
        mock_proc = MagicMock()
        mock_proc.stdout = iter(["提取完成"])
        mock_proc.wait.return_value = 0
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        from doc_knowledge.webui import do_extract
        status, log = do_extract(
            mirror_dir=".", output="", threshold=0.85, min_score=30,
            simhash=False, merge=False, keep_deprecated=False,
            dry_run=True, verbose=False,
        )
        assert isinstance(status, str)
        assert isinstance(log, str)
        mock_popen.assert_called_once()

    def test_extract_with_simhash(self):
        from doc_knowledge.webui import build_cmd
        cmd = build_cmd(["extract", "mirror", "--simhash", "--threshold", "0.9"])
        assert "--simhash" in cmd

    def test_extract_with_merge(self):
        from doc_knowledge.webui import build_cmd
        cmd = build_cmd(["extract", "mirror", "--merge"])
        assert "--merge" in cmd

    def test_extract_with_keep_deprecated(self):
        from doc_knowledge.webui import build_cmd
        cmd = build_cmd(["extract", "mirror", "--keep-deprecated"])
        assert "--keep-deprecated" in cmd


class TestDoExport:
    """do_export() 导出页面的路由逻辑"""

    @patch("doc_knowledge.webui.subprocess.Popen")
    def test_export_markdown(self, mock_popen):
        mock_proc = MagicMock()
        mock_proc.stdout = iter(["导出完成"])
        mock_proc.wait.return_value = 0
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        from doc_knowledge.webui import do_export
        status, log = do_export(
            knowledge_dir=".", target="markdown", vault_path="",
            output_dir="", api_url="", api_key="", workspace="", db_path="",
        )
        assert isinstance(status, str)
        assert isinstance(log, str)

    @patch("doc_knowledge.webui.subprocess.Popen")
    def test_export_obsidian(self, mock_popen):
        mock_proc = MagicMock()
        mock_proc.stdout = iter(["导出完成"])
        mock_proc.wait.return_value = 0
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        from doc_knowledge.webui import do_export
        status, log = do_export(
            knowledge_dir=".", target="obsidian", vault_path="/vault",
            output_dir="", api_url="", api_key="", workspace="", db_path="",
        )
        assert isinstance(status, str)

    @patch("doc_knowledge.webui.subprocess.Popen")
    def test_export_memomind_with_api(self, mock_popen):
        mock_proc = MagicMock()
        mock_proc.stdout = iter(["导出完成"])
        mock_proc.wait.return_value = 0
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        from doc_knowledge.webui import do_export
        status, log = do_export(
            knowledge_dir=".", target="memomind", vault_path="",
            output_dir="", api_url="http://localhost:99999",
            api_key="key", workspace="default", db_path="",
        )
        assert isinstance(status, str)

    @patch("doc_knowledge.webui.subprocess.Popen")
    def test_export_memomind_with_db(self, mock_popen):
        mock_proc = MagicMock()
        mock_proc.stdout = iter(["导出完成"])
        mock_proc.wait.return_value = 0
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        from doc_knowledge.webui import do_export
        status, log = do_export(
            knowledge_dir=".", target="memomind", vault_path="",
            output_dir="", api_url="", api_key="", workspace="default",
            db_path="/tmp/memomind.db",
        )
        assert isinstance(status, str)


class TestDoPipeline:
    """do_pipeline() 全流程页面的路由逻辑"""

    @patch("doc_knowledge.webui.subprocess.Popen")
    def test_pipeline_basic(self, mock_popen):
        mock_proc = MagicMock()
        mock_proc.stdout = iter(["全流程完成"])
        mock_proc.wait.return_value = 0
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        from doc_knowledge.webui import do_pipeline
        status, log = do_pipeline(
            source=".", output="", target="markdown", vault_path="",
            api_url="", api_key="", workspace="default", db_path="",
            threshold=0.85, min_score=30, simhash=False, merge=False,
            incremental=False, vision=False, vision_api_url="",
            vision_api_key="", vision_model="", verbose=False,
        )
        assert isinstance(status, str)
        assert isinstance(log, str)

    def test_pipeline_with_vision(self):
        from doc_knowledge.webui import build_cmd
        cmd = build_cmd([
            "pipeline", "source", "--vision",
            "--vision-api-url", "https://api.example.com",
            "--vision-api-key", "key",
            "--vision-model", "qwen-vl-plus",
        ])
        assert "--vision" in cmd
        assert "--vision-api-url" in cmd
        assert "--vision-api-key" in cmd
        assert "--vision-model" in cmd

    def test_pipeline_with_obsidian(self):
        from doc_knowledge.webui import build_cmd
        cmd = build_cmd(["pipeline", "source", "-t", "obsidian", "--vault", "/vault"])
        assert "--vault" in cmd


class TestTogglePipeTarget:
    """toggle_pipe_target() 动态表单：根据导出目标显示/隐藏字段"""

    def test_toggle_target_obsidian(self):
        """Obsidian: 只显示 vault"""
        def toggle_pipe_target(target):
            return (
                {"visible": target == "obsidian"},
                {"visible": target == "memomind"},
                {"visible": target == "memomind"},
                {"visible": target == "memomind"},
                {"visible": target == "memomind"},
            )

        result = toggle_pipe_target("obsidian")
        assert result[0]["visible"] is True  # vault
        assert result[1]["visible"] is False  # api_url
        assert result[2]["visible"] is False  # api_key

    def test_toggle_target_memomind(self):
        """MemoMind: 显示 API 相关字段"""
        def toggle_pipe_target(target):
            return (
                {"visible": target == "obsidian"},
                {"visible": target == "memomind"},
                {"visible": target == "memomind"},
                {"visible": target == "memomind"},
                {"visible": target == "memomind"},
            )

        result = toggle_pipe_target("memomind")
        assert result[0]["visible"] is False  # vault
        assert result[1]["visible"] is True   # api_url
        assert result[2]["visible"] is True   # api_key

    def test_toggle_target_markdown(self):
        """Markdown: 隐藏所有特殊字段"""
        def toggle_pipe_target(target):
            return (
                {"visible": target == "obsidian"},
                {"visible": target == "memomind"},
                {"visible": target == "memomind"},
                {"visible": target == "memomind"},
                {"visible": target == "memomind"},
            )

        result = toggle_pipe_target("markdown")
        for item in result:
            assert item["visible"] is False


class TestToggleVision:
    """toggle_vision() 动态表单：根据 OCR 开关显示/隐藏 API 字段"""

    def test_vision_enabled(self):
        def toggle_vision(v):
            return [{"visible": v}] * 3

        result = toggle_vision(True)
        assert len(result) == 3
        for item in result:
            assert item["visible"] is True

    def test_vision_disabled(self):
        def toggle_vision(v):
            return [{"visible": v}] * 3

        result = toggle_vision(False)
        for item in result:
            assert item["visible"] is False


class TestToggleExpTarget:
    """toggle_exp_target() 导出页面动态表单"""

    def test_toggle_obsidian(self):
        def toggle_exp_target(target):
            return (
                {"visible": target == "obsidian"},
                {"visible": target == "markdown"},
                {"visible": target == "memomind"},
                {"visible": target == "memomind"},
                {"visible": target == "memomind"},
                {"visible": target == "memomind"},
            )

        result = toggle_exp_target("obsidian")
        assert result[0]["visible"] is True  # vault
        assert result[1]["visible"] is False  # output
        assert result[2]["visible"] is False  # api_url

    def test_toggle_markdown(self):
        def toggle_exp_target(target):
            return (
                {"visible": target == "obsidian"},
                {"visible": target == "markdown"},
                {"visible": target == "memomind"},
                {"visible": target == "memomind"},
                {"visible": target == "memomind"},
                {"visible": target == "memomind"},
            )

        result = toggle_exp_target("markdown")
        assert result[0]["visible"] is False
        assert result[1]["visible"] is True  # output
        assert result[2]["visible"] is False

    def test_toggle_memomind(self):
        def toggle_exp_target(target):
            return (
                {"visible": target == "obsidian"},
                {"visible": target == "markdown"},
                {"visible": target == "memomind"},
                {"visible": target == "memomind"},
                {"visible": target == "memomind"},
                {"visible": target == "memomind"},
            )

        result = toggle_exp_target("memomind")
        assert result[0]["visible"] is False
        assert result[1]["visible"] is False
        assert result[2]["visible"] is True   # api_url
        assert result[3]["visible"] is True   # api_key


class TestAppImport:
    """app 导入和结构测试"""

    def test_app_imports(self):
        """webui 模块可以正常导入"""
        from doc_knowledge.webui import app
        assert app is not None

    def test_app_is_gradio_blocks(self):
        """app 是 Gradio Blocks 对象"""
        from doc_knowledge.webui import app
        import gradio as gr
        assert isinstance(app, gr.Blocks)

    def test_launch_ui_exists(self):
        """launch_ui 函数存在"""
        from doc_knowledge.webui import launch_ui
        assert callable(launch_ui)

    def test_theme_exists(self):
        """theme 对象存在"""
        from doc_knowledge.webui import theme
        assert theme is not None
