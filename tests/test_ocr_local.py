"""本地 OCR 服务测试（Tesseract）"""
from pathlib import Path

import pytest


def _make_text_image(path: Path, text: str = "Hello World 测试中文"):
    """创建含文字的图片"""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (400, 100), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    # 画文字和非纯色背景
    for x in range(0, 400, 5):
        draw.line([(x, 0), (x, 100)], fill=(250, 250, 252) if x % 10 == 0 else (255, 255, 255))
    draw.text((20, 30), text, fill=(0, 0, 0))
    img.save(path)
    return path


class TestLocalOCRService:
    """Tesseract 本地 OCR"""

    def test_engine_selection_tesseract(self):
        from doc_knowledge.ocr.local import LocalOCRService

        svc = LocalOCRService(engine="tesseract", lang="eng")
        assert svc.engine == "tesseract"

    def test_engine_selection_paddleocr_raises(self):
        from doc_knowledge.ocr.local import LocalOCRService

        with pytest.raises(NotImplementedError, match="PaddleOCR"):
            LocalOCRService(engine="paddleocr")

    def test_recognize_english_text(self, tmp_path):
        """识别英文文字"""
        from doc_knowledge.ocr.local import LocalOCRService

        img_path = tmp_path / "en.png"
        _make_text_image(img_path, "Hello World Test OCR")

        svc = LocalOCRService(engine="tesseract", lang="eng")
        results = svc.recognize_batch([img_path])
        assert img_path in results
        assert "Hello" in results[img_path]

    def test_recognize_chinese_text(self, tmp_path):
        """识别中英文混合"""
        from doc_knowledge.ocr.local import LocalOCRService

        img_path = tmp_path / "cn.png"
        _make_text_image(img_path, "文档测试 中文识别 OCR")

        svc = LocalOCRService(engine="tesseract", lang="chi_sim+eng")
        results = svc.recognize_batch([img_path])
        assert img_path in results
        # Tesseract 中文精度有限，至少应该识别出一些字符
        assert len(results[img_path].strip()) > 0

    def test_recognize_batch(self, tmp_path):
        from doc_knowledge.ocr.local import LocalOCRService

        images = []
        for i, text in enumerate(["Page One", "Page Two", "Page Three"]):
            p = tmp_path / f"img{i}.png"
            _make_text_image(p, text)
            images.append(p)

        svc = LocalOCRService(engine="tesseract", lang="eng")
        results = svc.recognize_batch(images)
        assert len(results) == 3
        assert "Page One" in results[images[0]]

    def test_recognize_empty_list(self):
        from doc_knowledge.ocr.local import LocalOCRService

        svc = LocalOCRService(engine="tesseract", lang="eng")
        assert svc.recognize_batch([]) == {}

    def test_recognize_nonexistent_file(self, tmp_path):
        from doc_knowledge.ocr.local import LocalOCRService

        svc = LocalOCRService(engine="tesseract", lang="eng")
        results = svc.recognize_batch([tmp_path / "nope.png"])
        assert "[文件不存在" in results[tmp_path / "nope.png"]


class TestFactoryWithLocal:
    """工厂函数创建本地 OCR 服务"""

    def test_local_mode_creates_local_service(self):
        from doc_knowledge.config import Config
        from doc_knowledge.ocr import create_ocr_service
        from doc_knowledge.ocr.local import LocalOCRService

        cfg = Config()
        cfg.ocr.enabled = True
        cfg.ocr.mode = "local"
        cfg.ocr.local.engine = "tesseract"
        cfg.ocr.local.lang = "eng"

        svc = create_ocr_service(cfg)
        assert isinstance(svc, LocalOCRService)
