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


class TestTesseractDiscovery:
    """Tesseract 可执行文件查找逻辑"""

    def test_uses_path_when_available(self, monkeypatch):
        """shutil.which 找到 tesseract 时应优先使用"""
        import shutil as _shutil
        from doc_knowledge.ocr.local import LocalOCRService

        fake_path = "/usr/local/bin/tesseract"
        monkeypatch.setattr(_shutil, "which", lambda cmd: fake_path if cmd == "tesseract" else None)
        monkeypatch.delenv("TESSERACT_CMD", raising=False)

        assert LocalOCRService._find_tesseract_cmd() == fake_path

    def test_falls_back_to_env_var(self, monkeypatch):
        """shutil.which 找不到时回退到 TESSERACT_CMD 环境变量"""
        import shutil as _shutil
        from doc_knowledge.ocr.local import LocalOCRService

        monkeypatch.setattr(_shutil, "which", lambda cmd: None)
        monkeypatch.setenv("TESSERACT_CMD", "/custom/path/tesseract")

        assert LocalOCRService._find_tesseract_cmd() == "/custom/path/tesseract"

    def test_returns_none_when_not_found(self, monkeypatch, tmp_path):
        """都找不到时返回 None，让 pytesseract 用自己默认值"""
        import os as _os
        import shutil as _shutil
        from doc_knowledge.ocr.local import LocalOCRService

        monkeypatch.setattr(_shutil, "which", lambda cmd: None)
        monkeypatch.delenv("TESSERACT_CMD", raising=False)
        # 把 ProgramFiles 指向一个不含 Tesseract 的临时目录，让第 3 层 fallback 失败
        monkeypatch.setenv("ProgramFiles", str(tmp_path))

        assert LocalOCRService._find_tesseract_cmd() is None

    def test_windows_fallback_finds_program_files(self, monkeypatch, tmp_path):
        """Windows 上 PATH 和环境变量都没有时，应回退到 %ProgramFiles%\\Tesseract-OCR"""
        import os as _os
        import shutil as _shutil
        from doc_knowledge.ocr.local import LocalOCRService

        if _os.name != "nt":
            pytest.skip("仅 Windows 适用")

        # 构造一个伪 Program Files 目录，含 tesseract.exe
        fake_pf = tmp_path / "fake_program_files"
        tesseract_dir = fake_pf / "Tesseract-OCR"
        tesseract_dir.mkdir(parents=True)
        fake_exe = tesseract_dir / "tesseract.exe"
        fake_exe.write_bytes(b"")

        monkeypatch.setattr(_shutil, "which", lambda cmd: None)
        monkeypatch.delenv("TESSERACT_CMD", raising=False)
        monkeypatch.setenv("ProgramFiles", str(fake_pf))

        assert LocalOCRService._find_tesseract_cmd() == str(fake_exe)

    def test_no_hardcoded_windows_path(self):
        """源码不应再含硬编码的 Windows Tesseract 路径"""
        from doc_knowledge.ocr import local as local_module
        import inspect

        source = inspect.getsource(local_module)
        assert "Program Files\\Tesseract-OCR" not in source
        assert "Program Files/Tesseract-OCR" not in source


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
