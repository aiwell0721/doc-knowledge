"""slide 失败页补跑机制测试（自动二轮 + retry-slide CLI）

覆盖：
- SlideFusionService.retry_pages（渲染源 PPTX 后仅识别指定页）
- converters._update_slide_blockquotes（补跑后更新已有 markdown）
- CLI retry-slide 命令（解析 frontmatter source + 失败页 → 识别 → 写回）
"""

import json
import subprocess
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

import pytest

from doc_knowledge.converters import _update_slide_blockquotes
from doc_knowledge.ocr.slide import SlideFusionService


class _SlideAPIHandler(BaseHTTPRequestHandler):
    """模拟 OpenAI 兼容 API"""

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        assert body["messages"][0]["role"] == "system"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        resp = json.dumps(
            {"choices": [{"message": {"content": '{"page_summary": "测试页"}'}}]}
        )
        self.wfile.write(resp.encode())

    def log_message(self, format, *args):
        pass


@pytest.fixture
def mock_api_server():
    server = HTTPServer(("127.0.0.1", 0), _SlideAPIHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


def _make_minimal_pdf(path: Path, pages: int = 3):
    import fitz

    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page(width=400, height=300)
        page.insert_text((50, 80), f"Slide {i+1} test content")
    doc.save(str(path))
    doc.close()
    return path


def _fake_soffice(cmd, **kwargs):
    """fake soffice：生成与输入同 stem 的 PDF 到 --outdir"""
    i = cmd.index("--outdir")
    outdir = Path(cmd[i + 1])
    stem = Path(cmd[-1]).stem
    _make_minimal_pdf(outdir / f"{stem}.pdf", pages=3)
    return subprocess.CompletedProcess(cmd, 0)


class TestRetryPages:
    """retry_pages：渲染源 PPTX 后仅识别指定页（不浪费额度重跑成功页）"""

    def test_recognizes_only_target_pages(self, mock_api_server, tmp_path, monkeypatch):
        svc = SlideFusionService(api_url=mock_api_server, api_key="k")
        pptx = tmp_path / "test.pptx"
        pptx.write_bytes(b"PK")

        monkeypatch.setattr(
            "doc_knowledge.ocr.slide._find_soffice", lambda: "C:/fake/soffice.exe"
        )
        monkeypatch.setattr(subprocess, "run", _fake_soffice)

        results = svc.retry_pages(pptx, tmp_path, page_numbers=[1, 3])
        assert set(results) == {1, 3}  # 仅识别指定页，不识别 page2
        for num, text in results.items():
            assert "page_summary" in text

    def test_empty_page_list_returns_empty(self, tmp_path, monkeypatch):
        svc = SlideFusionService(api_url="http://x", api_key="k")
        pptx = tmp_path / "test.pptx"
        pptx.write_bytes(b"PK")

        monkeypatch.setattr(
            "doc_knowledge.ocr.slide._find_soffice", lambda: "C:/fake/soffice.exe"
        )
        monkeypatch.setattr(subprocess, "run", _fake_soffice)

        results = svc.retry_pages(pptx, tmp_path, page_numbers=[])
        assert results == {}


class TestUpdateSlideBlockquotes:
    """_update_slide_blockquotes：补跑后更新已有 markdown"""

    def test_replace_fallback_block(self):
        md = (
            "<!-- Slide number: 1 -->\n\n"
            "> 📊 **整页理解**: ⚠️ 本页图表语义识别失败（VLM 请求异常），原始文字已保留\n\n"
            "内容A\n\n"
            "<!-- Slide number: 2 -->\n\n"
            '> 📊 **整页理解**: {"page_summary": "成功"}\n\n'
            "内容B\n"
        )
        out = _update_slide_blockquotes(md, {1: '{"page_summary": "补跑成功"}'})

        assert "补跑成功" in out
        assert "识别失败" not in out              # 降级提示被替换
        assert '"page_summary": "成功"' in out   # 非目标页保持原样
        assert out.count("整页理解") == 2         # 不重复注入

    def test_insert_missing_block(self):
        """旧版空串丢失页（无 blockquote）→ 补跑后插入"""
        md = "<!-- Slide number: 1 -->\n\n内容A\n"
        out = _update_slide_blockquotes(md, {1: '{"page_summary": "补跑成功"}'})
        assert "整页理解" in out
        assert "补跑成功" in out

    def test_non_target_pages_untouched(self):
        md = (
            "<!-- Slide number: 1 -->\n\n内容A\n\n"
            "<!-- Slide number: 2 -->\n\n内容B\n"
        )
        out = _update_slide_blockquotes(md, {2: '{"page_summary": "第二页补跑"}'})
        # 第 1 页无结果，不注入
        assert out.count("整页理解") == 1
        assert "第二页补跑" in out.split("<!-- Slide number: 2 -->")[1]

    def test_still_failed_stays_fallback(self):
        """补跑仍失败的页，保留/更新降级提示（不注入错误堆栈）"""
        md = (
            "<!-- Slide number: 1 -->\n\n"
            "> 📊 **整页理解**: ⚠️ 本页图表语义识别失败（VLM 请求异常），原始文字已保留\n\n"
            "内容A\n"
        )
        out = _update_slide_blockquotes(
            md, {1: "[图片识别失败: HTTP Error 429: Too Many Requests]"}
        )
        assert "识别失败" in out                 # 仍是降级提示
        assert "HTTP Error 429" not in out       # 不暴露错误堆栈

    def test_replace_legacy_error_block(self):
        """旧格式 md（错误堆栈 [图片识别失败...]）也能被替换，不残留重复块

        回归：真实 75 页 PPT 生成于降级提示功能之前，失败页为错误堆栈原文。
        _update_slide_blockquotes 删除旧块时需兼容该形态，否则新旧块叠加。
        """
        md = (
            "<!-- Slide number: 1 -->\n\n"
            "> 📊 **整页理解**: [图片识别失败: HTTP Error 429: Too Many Requests]\n\n"
            "内容A\n"
        )
        out = _update_slide_blockquotes(md, {1: '{"page_summary": "补跑成功"}'})

        assert "补跑成功" in out
        assert "HTTP Error 429" not in out       # 旧错误堆栈块被删除
        assert out.count("整页理解") == 1         # 不叠加新旧块


class TestRetrySlideCLI:
    """CLI retry-slide 命令：解析 source + 失败页 → 识别 → 写回 md"""

    def test_updates_markdown(self, tmp_path, monkeypatch):
        from click.testing import CliRunner

        from doc_knowledge.cli.retry_slide import retry_slide
        from doc_knowledge.ocr.slide import SlideFusionService

        src = tmp_path / "source.pptx"
        src.write_bytes(b"PK")
        md_path = tmp_path / "out.md"
        md_path.write_text(
            f"---\n"
            f'source: "file:///{src.as_posix()}"\n'
            "---\n"
            "<!-- Slide number: 1 -->\n\n"
            "> 📊 **整页理解**: ⚠️ 本页图表语义识别失败（VLM 请求异常），原始文字已保留\n\n"
            "内容A\n",
            encoding="utf-8",
        )

        monkeypatch.setattr(
            SlideFusionService, "retry_pages",
            lambda self, pptx, out, page_numbers, verbose=False: {
                1: '{"page_summary": "补跑成功"}'
            },
        )

        runner = CliRunner()
        result = runner.invoke(
            retry_slide,
            [str(md_path), "--ocr-api-url", "http://x", "--ocr-api-key", "k"],
        )
        assert result.exit_code == 0, result.output

        updated = md_path.read_text(encoding="utf-8")
        assert "补跑成功" in updated
        assert "识别失败" not in updated

    def test_legacy_error_placeholder_recognized(self, tmp_path, monkeypatch):
        """旧格式 md（错误堆栈 [图片识别失败...]）也能识别失败页并补跑

        回归：真实 75 页 PPT 生成于降级提示功能之前，失败页为错误堆栈原文，
        retry-slide 只匹配 ⚠️ 会导致\"无需补跑\"漏检。
        """
        from click.testing import CliRunner

        from doc_knowledge.cli.retry_slide import retry_slide
        from doc_knowledge.ocr.slide import SlideFusionService

        src = tmp_path / "source.pptx"
        src.write_bytes(b"PK")
        md_path = tmp_path / "out.md"
        md_path.write_text(
            f"---\n"
            f'source: "file:///{src.as_posix()}"\n'
            "---\n"
            "<!-- Slide number: 1 -->\n\n"
            "> 📊 **整页理解**: [图片识别失败: HTTP Error 429: Too Many Requests]\n\n"
            "内容A\n",
            encoding="utf-8",
        )

        monkeypatch.setattr(
            SlideFusionService, "retry_pages",
            lambda self, pptx, out, page_numbers, verbose=False: {
                1: '{"page_summary": "补跑成功"}'
            },
        )

        runner = CliRunner()
        result = runner.invoke(
            retry_slide,
            [str(md_path), "--ocr-api-url", "http://x", "--ocr-api-key", "k"],
        )
        assert result.exit_code == 0, result.output
        assert "1 个失败页" in result.output       # 旧格式失败页被识别

        updated = md_path.read_text(encoding="utf-8")
        assert "补跑成功" in updated
        assert "HTTP Error 429" not in updated     # 旧错误堆栈被替换

    def test_no_failed_pages_reports_idle(self, tmp_path, monkeypatch):
        from click.testing import CliRunner

        from doc_knowledge.cli.retry_slide import retry_slide

        src = tmp_path / "source.pptx"
        src.write_bytes(b"PK")
        md_path = tmp_path / "ok.md"
        md_path.write_text(
            f"---\n"
            f'source: "file:///{src.as_posix()}"\n'
            "---\n"
            "<!-- Slide number: 1 -->\n\n"
            '> 📊 **整页理解**: {"page_summary": "成功"}\n\n'
            "内容A\n",
            encoding="utf-8",
        )

        runner = CliRunner()
        result = runner.invoke(
            retry_slide,
            [str(md_path), "--ocr-api-url", "http://x", "--ocr-api-key", "k"],
        )
        assert result.exit_code == 0, result.output
        assert "无需补跑" in result.output
