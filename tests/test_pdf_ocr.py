"""PDF 页渲染 + OCR 集成测试"""
from pathlib import Path

import pytest


class TestPDFPageRendering:
    """PDF 页转图片"""

    def test_render_text_pdf_pages(self, tmp_path):
        """有文字层的 PDF 正常转换，不触发页面渲染"""
        from doc_knowledge.converters import convert_file

        # 用足够长的文本，避免被密度阈值误判为扫描件
        pdf_path = _create_text_pdf(
            tmp_path,
            "Hello World - this is a text-based PDF with enough content "
            "to pass the density check. The test verifies that real text "
            "documents are not mistakenly treated as scanned images."
        )
        markdown, images, image_map = convert_file(pdf_path, output_dir=tmp_path)
        assert "Hello World" in markdown
        assert images == 0  # 有文字层，不需要 OCR

    def test_render_image_based_pdf_pages(self, tmp_path):
        """无文字层的图片型 PDF — 渲染为页面图片"""
        from doc_knowledge.converters import _render_pdf_pages, _pdf_has_text_layer

        pdf_path = _create_image_pdf(tmp_path)
        assert not _pdf_has_text_layer(pdf_path), "图片型 PDF 应无文字层"

        page_images = _render_pdf_pages(pdf_path, tmp_path)
        assert len(page_images) == 2
        for p in page_images:
            assert p.exists()
            assert p.stat().st_size > 100  # 非空文件
            assert p.suffix == ".png"

    def test_nonexistent_pdf(self, tmp_path):
        """不存在的 PDF 文件 — 返回空列表"""
        from doc_knowledge.converters import _render_pdf_pages

        pdf_path = tmp_path / "not_exist.pdf"
        page_images = _render_pdf_pages(pdf_path, tmp_path)
        assert page_images == []

    def test_text_pdf_detection(self, tmp_path):
        """检测 PDF 是否有文字层"""
        from doc_knowledge.converters import _pdf_has_text_layer

        # 用足够多字符的真实文本，符合"平均每页 50+ 字符"密度阈值
        text_pdf = _create_text_pdf(
            tmp_path,
            "This is a sample document with enough content for density check. "
            "It contains multiple sentences to ensure the text layer detector "
            "correctly identifies this as a text-based PDF, not a scanned image."
        )
        image_pdf = _create_image_pdf(tmp_path)

        assert _pdf_has_text_layer(text_pdf)
        assert not _pdf_has_text_layer(image_pdf)

    def test_scanned_pdf_with_watermark_not_detected_as_text(self, tmp_path):
        """扫描件嵌入了页眉/页脚水印（每页 >10 但 <50 字符）不应被误判为文字 PDF"""
        from doc_knowledge.converters import _pdf_has_text_layer
        import fitz

        # 构造："扫描件 + 页眉水印"：3 页，每页嵌入约 25-30 字符的水印
        # 这正是旧实现的盲区：单页 >10 字符即判定有文字层
        pdf_path = tmp_path / "scanned_with_watermark.pdf"
        doc = fitz.open()
        for i in range(3):
            page = doc.new_page()
            page.insert_text((50, 30), f"Confidential - Page {i+1} of 3", fontsize=8)
        doc.save(str(pdf_path))
        doc.close()

        # 总字符数 ~75，3 页 → 平均 25/页 < 50 阈值
        assert not _pdf_has_text_layer(pdf_path), "水印级文字不应被认为是真正的文字层"

    def test_single_page_text_pdf_detected(self, tmp_path):
        """单页正常文字 PDF 应被识别为有文字层"""
        from doc_knowledge.converters import _pdf_has_text_layer

        pdf_path = _create_text_pdf(
            tmp_path,
            "A standard one-page document. " * 5  # ~150 字符
        )
        assert _pdf_has_text_layer(pdf_path)


class TestOCRIntegration:
    """convert_file 集成 OCR 处理图片型 PDF"""

    def test_image_pdf_with_ocr_disabled(self, tmp_path):
        """OCR 未启用 — 图片型 PDF 生成警告占位"""
        from doc_knowledge.converters import convert_file

        pdf_path = _create_image_pdf(tmp_path)
        markdown, images, image_map = convert_file(pdf_path, output_dir=tmp_path)

        # 应包含提示信息
        assert "OCR" in markdown or "图片型PDF" in markdown or "图片型 PDF" in markdown
        assert images > 0  # 页面渲染为图片

    def test_image_pdf_with_cloud_ocr(self, mock_api_server, tmp_path):
        """云端 OCR 启用 — 图片型 PDF 走 VLM 识别"""
        from doc_knowledge.config import Config
        from doc_knowledge.ocr import create_ocr_service
        from doc_knowledge.converters import convert_file

        cfg = Config()
        cfg.ocr.enabled = True
        cfg.ocr.mode = "cloud"
        cfg.ocr.cloud.api_url = mock_api_server
        cfg.ocr.cloud.api_key = "test-key"
        ocr_service = create_ocr_service(cfg)

        pdf_path = _create_image_pdf(tmp_path)
        markdown, images, image_map = convert_file(
            pdf_path, output_dir=tmp_path, ocr_service=ocr_service
        )

        assert "识别结果" in markdown
        assert images > 0


# ─── 辅助函数 ────────────────────────────────────────────

def _create_text_pdf(tmp_path: Path, text: str) -> Path:
    """创建有文字层的 PDF"""
    import fitz  # PyMuPDF

    pdf_path = tmp_path / "text_doc.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), text, fontsize=12)
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


def _create_image_pdf(tmp_path: Path) -> Path:
    """创建无文字层的图片型 PDF（2 页）"""
    from PIL import Image, ImageDraw

    import fitz

    pdf_path = tmp_path / "image_doc.pdf"
    doc = fitz.open()

    for i in range(2):
        # 创建含文字的图片（模拟扫描件）
        img = Image.new("RGB", (400, 300), color=(250, 250, 250))
        draw = ImageDraw.Draw(img)
        for y in range(0, 300, 30):
            draw.line([(0, y), (400, y)], fill=(200, 200, 200))
        draw.text((50, 50), f"Scanned Page {i+1}", fill=(0, 0, 0))
        draw.text((50, 80), "文档内容示例 - 测试数据", fill=(0, 0, 0))
        img_path = tmp_path / f"page_{i}.png"
        img.save(img_path)

        page = doc.new_page(width=400, height=300)
        page.insert_image(page.rect, filename=str(img_path))

    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


# ─── Mock API (与 test_ocr_service.py 共用逻辑) ──────────

import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler


class _MockAPIHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        # 有 system message 和 user message
        user_content = body["messages"][-1]["content"]
        if isinstance(user_content, list):
            img_item = user_content[0]
            assert img_item["image_url"]["url"].startswith("data:image/")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        resp = json.dumps(
            {"choices": [{"message": {"content": "识别结果：这是一份扫描文档，包含测试数据"}}]}
        )
        self.wfile.write(resp.encode())

    def log_message(self, format, *args):
        pass


@pytest.fixture
def mock_api_server():
    server = HTTPServer(("127.0.0.1", 0), _MockAPIHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
