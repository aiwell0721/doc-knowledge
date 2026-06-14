"""OCR 服务层测试"""
import base64
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

import pytest

from doc_knowledge.config import Config, OCRConfig, CloudOCRConfig, load_config
from doc_knowledge.ocr import create_ocr_service
from doc_knowledge.ocr.base import OCRService
from doc_knowledge.ocr.cloud import CloudOCRService


class _MockAPIHandler(BaseHTTPRequestHandler):
    """模拟 OpenAI 兼容 API"""

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        # content[0] 是 image_url, content[1] 是 text
        img_item = body["messages"][1]["content"][0]
        assert img_item["type"] == "image_url"
        assert img_item["image_url"]["url"].startswith("data:image/")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        resp = json.dumps(
            {"choices": [{"message": {"content": "识别结果：这是一张测试图片"}}]}
        )
        self.wfile.write(resp.encode())

    def log_message(self, format, *args):
        pass  # 静默日志


@pytest.fixture
def mock_api_server():
    """启动模拟 API 服务器"""
    server = HTTPServer(("127.0.0.1", 0), _MockAPIHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


def _make_test_image(path: Path, size=(200, 200)):
    """创建含文字的测试图片，避免被纯色过滤器拦截"""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", size, color=(240, 240, 240))
    draw = ImageDraw.Draw(img)
    # 画一些线条和形状模拟真实内容
    for i in range(0, size[0], 20):
        draw.line([(i, 0), (i, size[1])], fill=(180, 180, 180))
    for j in range(0, size[1], 20):
        draw.line([(0, j), (size[0], j)], fill=(180, 180, 180))
    draw.rectangle([30, 30, 170, 70], outline=(0, 0, 0), width=2)
    draw.text((40, 40), "Test OCR", fill=(0, 0, 0))
    img.save(path)
    return path


@pytest.fixture
def sample_image(tmp_path):
    img_path = tmp_path / "test.png"
    return _make_test_image(img_path)


class TestOCRServiceABC:
    """抽象基类"""

    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            OCRService()


class TestCloudOCRService:
    """云端 OCR 服务"""

    def test_create_service(self, mock_api_server):
        svc = CloudOCRService(
            api_url=mock_api_server, api_key="test-key", model="gpt-4o"
        )
        assert svc.api_url == mock_api_server
        assert svc.model == "gpt-4o"

    def test_recognize_single_image(self, mock_api_server, sample_image):
        svc = CloudOCRService(
            api_url=mock_api_server, api_key="test-key", model="gpt-4o"
        )
        result = svc.recognize_batch([sample_image])
        assert sample_image in result
        assert "识别结果" in result[sample_image]

    def test_recognize_batch(self, mock_api_server, tmp_path):
        images = []
        for i in range(3):
            p = tmp_path / f"img{i}.png"
            _make_test_image(p)
            images.append(p)

        svc = CloudOCRService(
            api_url=mock_api_server, api_key="test-key", model="gpt-4o"
        )
        results = svc.recognize_batch(images)
        assert len(results) == 3
        for img in images:
            assert img in results

    def test_recognize_empty_list(self, mock_api_server):
        svc = CloudOCRService(
            api_url=mock_api_server, api_key="test-key", model="gpt-4o"
        )
        results = svc.recognize_batch([])
        assert results == {}

    def test_auth_header(self, mock_api_server, sample_image):
        svc = CloudOCRService(
            api_url=mock_api_server, api_key="bearer-token-xyz", model="gpt-4o"
        )
        results = svc.recognize_batch([sample_image])
        assert sample_image in results  # 不抛异常即认证通过


class TestCreateOCRService:
    """工厂函数 — 根据配置创建服务"""

    def test_disabled_returns_none(self, tmp_path):
        from doc_knowledge.config import Config

        cfg = Config()
        cfg.ocr.enabled = False
        svc = create_ocr_service(cfg)
        assert svc is None

    def test_cloud_mode_creates_cloud_service(self, mock_api_server):
        from doc_knowledge.config import Config

        cfg = Config()
        cfg.ocr.enabled = True
        cfg.ocr.mode = "cloud"
        cfg.ocr.cloud.api_url = mock_api_server
        cfg.ocr.cloud.api_key = "test-key"
        svc = create_ocr_service(cfg)
        assert isinstance(svc, CloudOCRService)

    def test_local_mode_creates_local_service(self):
        from doc_knowledge.ocr.local import LocalOCRService

        cfg = Config()
        cfg.ocr.enabled = True
        cfg.ocr.mode = "local"
        svc = create_ocr_service(cfg)
        assert isinstance(svc, LocalOCRService)

    def test_hybrid_mode_not_implemented_yet(self):
        cfg = Config()
        cfg.ocr.enabled = True
        cfg.ocr.mode = "hybrid"
        with pytest.raises(NotImplementedError, match="混合 OCR"):
            create_ocr_service(cfg)
