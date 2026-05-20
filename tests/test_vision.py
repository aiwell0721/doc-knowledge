"""
Tests for vision.py — ImageFilter and LLMVisionService.

Covers:
- ImageFilter: should_recognize, _is_solid_color, all methods
- LLMVisionService: recognize_image, recognize_images_batch
- Image filtering logic, batch recognition, error handling
"""

import pytest
import json
import io
from pathlib import Path
from unittest.mock import patch, MagicMock
from PIL import Image
from doc_knowledge.vision import ImageFilter, LLMVisionService


# ── Image helpers ──

def _create_test_image(tmp_path: Path, filename: str, size: tuple = (100, 100),
                       color: tuple = (128, 64, 32), fmt: str = "PNG") -> Path:
    """Create a test image file."""
    filepath = tmp_path / filename
    img = Image.new("RGB", size, color)
    img.save(str(filepath), format=fmt)
    return filepath


def _create_noise_image(tmp_path: Path, filename: str, size: tuple = (200, 200)) -> Path:
    """Create an image with random-looking pixel variation (not solid color)."""
    filepath = tmp_path / filename
    img = Image.new("RGB", size)
    pixels = img.load()
    for x in range(size[0]):
        for y in range(size[1]):
            pixels[x, y] = ((x * 7 + y * 13) % 256, (x * 11 + y * 3) % 256, (x + y * 17) % 256)
    img.save(str(filepath), format="PNG")
    return filepath


def _create_gradient_image(tmp_path: Path, filename: str,
                            size: tuple = (100, 100)) -> Path:
    """Create a gradient image (should NOT be filtered out)."""
    filepath = tmp_path / filename
    img = Image.new("RGB", size)
    pixels = img.load()
    for x in range(size[0]):
        for y in range(size[1]):
            pixels[x, y] = (x * 255 // size[0], y * 255 // size[1], 128)
    img.save(str(filepath), format="PNG")
    return filepath


def _create_small_file(tmp_path: Path, filename: str) -> Path:
    """Create a tiny file (below min_size=500) that's not a real image."""
    filepath = tmp_path / filename
    filepath.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    return filepath


# ── Mock helpers ──

def _make_mock_response(content="ok"):
    """Create a mock response object for urlopen."""
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "choices": [{"message": {"content": content}}]
    }).encode("utf-8")
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)
    return mock_response


def _mock_urlopen(content="ok"):
    """Create a mock urlopen function that accepts **kwargs (for timeout)."""
    def mock_fn(req, **kwargs):
        return _make_mock_response(content)
    return mock_fn


# ═══════════════════════════════════════
# ImageFilter Tests
# ═══════════════════════════════════════

class TestImageFilterInit:
    """ImageFilter 初始化"""

    def test_default_params(self):
        f = ImageFilter()
        assert f.min_size == 500
        assert f.min_resolution == 50
        assert f.max_similarity_threshold == 0.95

    def test_custom_params(self):
        f = ImageFilter(min_size=1000, min_resolution=100, max_similarity_threshold=0.8)
        assert f.min_size == 1000
        assert f.min_resolution == 100
        assert f.max_similarity_threshold == 0.8


class TestImageFilterShouldRecognize:
    """should_recognize() 判断图片是否需要识别"""

    def test_nonexistent_file(self, tmp_path):
        f = ImageFilter()
        should, reason = f.should_recognize(tmp_path / "nonexistent.png")
        assert should is False
        assert "不存在" in reason

    def test_file_too_small(self, tmp_path):
        """文件太小应被过滤"""
        fp = _create_small_file(tmp_path, "tiny.png")
        assert fp.stat().st_size < 500
        f = ImageFilter()
        should, reason = f.should_recognize(fp)
        assert should is False
        assert "太小" in reason

    def test_resolution_too_low(self, tmp_path):
        """分辨率太低应被过滤（文件够大但分辨率低）"""
        # 49x49 BMP is below min_resolution=50, and BMP is large enough
        fp = _create_test_image(tmp_path, "lowres.bmp", size=(49, 49), fmt="BMP")
        assert fp.stat().st_size > 500
        f = ImageFilter()
        should, reason = f.should_recognize(fp)
        assert should is False
        assert "分辨率太低" in reason

    def test_solid_color_image(self, tmp_path):
        """纯色图片应被过滤"""
        fp = _create_test_image(tmp_path, "solid.png", size=(200, 200), color=(200, 200, 200))
        assert fp.stat().st_size > 500
        f = ImageFilter()
        should, reason = f.should_recognize(fp)
        assert should is False
        assert "纯色" in reason

    def test_gradient_image(self, tmp_path):
        """渐变/有内容的图片应通过"""
        fp = _create_gradient_image(tmp_path, "gradient.png", size=(200, 200))
        assert fp.stat().st_size > 500
        f = ImageFilter()
        should, reason = f.should_recognize(fp)
        assert should is True
        assert "需要识别" in reason

    def test_noise_image(self, tmp_path):
        """有像素变化的图片应通过（不被当作纯色）"""
        fp = _create_noise_image(tmp_path, "noise.png", size=(200, 200))
        assert fp.stat().st_size > 500
        f = ImageFilter()
        should, reason = f.should_recognize(fp)
        assert should is True
        assert "需要识别" in reason


class TestImageFilterIsSolidColor:
    """_is_solid_color() 纯色检测"""

    def test_solid_white(self, tmp_path):
        fp = _create_test_image(tmp_path, "white.png", color=(255, 255, 255), size=(200, 200))
        f = ImageFilter()
        assert f._is_solid_color(fp) is True

    def test_solid_black(self, tmp_path):
        fp = _create_test_image(tmp_path, "black.png", color=(0, 0, 0), size=(200, 200))
        f = ImageFilter()
        assert f._is_solid_color(fp) is True

    def test_solid_gray(self, tmp_path):
        fp = _create_test_image(tmp_path, "gray.png", color=(128, 128, 128), size=(200, 200))
        f = ImageFilter()
        assert f._is_solid_color(fp) is True

    def test_gradient_not_solid(self, tmp_path):
        fp = _create_gradient_image(tmp_path, "gradient.png", size=(200, 200))
        f = ImageFilter()
        assert f._is_solid_color(fp) is False


# ═══════════════════════════════════════
# LLMVisionService Tests
# ═══════════════════════════════════════

class TestLLMVisionServiceInit:
    """LLMVisionService 初始化"""

    def test_basic_init(self):
        svc = LLMVisionService(
            api_url="https://api.example.com",
            api_key="test-key",
        )
        assert "chat/completions" in svc.api_url
        assert svc.api_key == "test-key"
        assert svc.model == "qwen-vl-plus"
        assert svc.timeout == 120
        assert svc.max_workers == 5
        assert isinstance(svc.filter, ImageFilter)

    def test_custom_params(self):
        svc = LLMVisionService(
            api_url="https://custom.api.com/v1/",
            api_key="key123",
            model="gpt-4-vision",
            timeout=60,
            max_workers=3,
            max_image_size=1024 * 1024,
        )
        assert svc.api_url == "https://custom.api.com/v1/chat/completions"
        assert svc.model == "gpt-4-vision"
        assert svc.timeout == 60
        assert svc.max_workers == 3

    def test_custom_system_prompt(self):
        svc = LLMVisionService(
            api_url="https://api.example.com",
            api_key="key",
            system_prompt="Custom prompt",
        )
        assert svc.system_prompt == "Custom prompt"

    def test_api_url_trailing_slash_removed(self):
        svc = LLMVisionService(
            api_url="https://api.example.com/",
            api_key="key",
        )
        assert not svc.api_url.endswith("/")


class TestLLMVisionServiceRecognizeImage:
    """recognize_image() 单张图片识别"""

    def test_nonexistent_file(self, tmp_path):
        svc = LLMVisionService(api_url="https://api.example.com", api_key="key")
        result = svc.recognize_image(tmp_path / "nonexistent.png")
        assert "不存在" in result

    def test_successful_recognition_mock(self, tmp_path):
        """模拟成功的图片识别"""
        fp = _create_noise_image(tmp_path, "test.png", size=(200, 200))
        with patch("doc_knowledge.vision.urllib.request.urlopen",
                   side_effect=_mock_urlopen("This is a test image description.")):
            svc = LLMVisionService(api_url="https://api.example.com", api_key="key")
            result = svc.recognize_image(fp)
        assert "test image description" in result

    def test_url_error(self, tmp_path):
        """网络错误处理"""
        fp = _create_noise_image(tmp_path, "test.png", size=(200, 200))
        import urllib.error
        with patch("doc_knowledge.vision.urllib.request.urlopen",
                   side_effect=urllib.error.URLError("Connection refused")):
            svc = LLMVisionService(api_url="https://api.example.com", api_key="key")
            result = svc.recognize_image(fp)
        assert "失败" in result or "Connection refused" in result

    def test_malformed_response(self, tmp_path):
        """API 返回格式错误的响应"""
        fp = _create_noise_image(tmp_path, "test.png", size=(200, 200))
        with patch("doc_knowledge.vision.urllib.request.urlopen", return_value=_make_mock_response(
                content=None)) as mock_urlopen:
            # Make read return malformed JSON
            mock_urlopen.return_value.read.return_value = json.dumps({
                "unexpected_key": "unexpected_value"
            }).encode("utf-8")
            svc = LLMVisionService(api_url="https://api.example.com", api_key="key")
            result = svc.recognize_image(fp)
        assert "解析失败" in result or "KeyError" in result

    def test_mime_type_jpeg(self, tmp_path):
        """JPEG 图片使用正确的 MIME 类型"""
        fp = _create_test_image(tmp_path, "test.jpg", size=(200, 200), fmt="JPEG")
        captured = {}

        def capture(req, **kwargs):
            captured["data"] = json.loads(req.data)
            return _make_mock_response("ok")

        with patch("doc_knowledge.vision.urllib.request.urlopen", side_effect=capture):
            svc = LLMVisionService(api_url="https://api.example.com", api_key="key")
            svc.recognize_image(fp)

        content = captured["data"]["messages"][1]["content"]
        image_url = content[0]["image_url"]["url"]
        assert "image/jpeg" in image_url

    def test_mime_type_png(self, tmp_path):
        """PNG 图片使用正确的 MIME 类型"""
        fp = _create_test_image(tmp_path, "test.png", size=(200, 200), fmt="PNG")
        captured = {}

        def capture(req, **kwargs):
            captured["data"] = json.loads(req.data)
            return _make_mock_response("ok")

        with patch("doc_knowledge.vision.urllib.request.urlopen", side_effect=capture):
            svc = LLMVisionService(api_url="https://api.example.com", api_key="key")
            svc.recognize_image(fp)

        content = captured["data"]["messages"][1]["content"]
        image_url = content[0]["image_url"]["url"]
        assert "image/png" in image_url

    def test_auth_header(self, tmp_path):
        """请求包含正确的 Authorization header"""
        fp = _create_noise_image(tmp_path, "test.png", size=(200, 200))
        captured = {}

        def capture(req, **kwargs):
            captured["auth"] = req.get_header("Authorization")
            # urllib stores header as 'Content-type' (capitalized)
            captured["ctype"] = req.headers.get("Content-type")
            return _make_mock_response("ok")

        with patch("doc_knowledge.vision.urllib.request.urlopen", side_effect=capture):
            svc = LLMVisionService(api_url="https://api.example.com", api_key="secret-key-123")
            svc.recognize_image(fp)

        assert captured["auth"] == "Bearer secret-key-123"
        assert captured["ctype"] == "application/json"

    def test_image_compression(self, tmp_path):
        """大图片会被压缩（使用 BMP 保证超过 2MB）"""
        # BMP is uncompressed; 2000x2000 RGB = ~12MB
        fp = _create_test_image(tmp_path, "large.bmp", size=(2000, 2000), fmt="BMP")
        # Verify size > 2MB
        size_mb = fp.stat().st_size / (1024 * 1024)
        assert size_mb > 2, f"Image too small: {size_mb:.1f}MB"

        captured = {}

        def capture(req, **kwargs):
            # Capture the actual image data sent to verify compression happened
            payload = json.loads(req.data)
            img_url = payload["messages"][1]["content"][0]["image_url"]["url"]
            # Extract base64 data size
            import base64 as b64
            b64_data = img_url.split("base64,")[1]
            decoded_size = len(b64.b64decode(b64_data))
            captured["sent_size"] = decoded_size
            return _make_mock_response("compressed")

        with patch("doc_knowledge.vision.urllib.request.urlopen", side_effect=capture):
            svc = LLMVisionService(
                api_url="https://api.example.com",
                api_key="key",
                max_image_size=2 * 1024 * 1024,
            )
            result = svc.recognize_image(fp)

        # The sent image should be smaller than original (was compressed)
        assert captured["sent_size"] < fp.stat().st_size
        assert "compressed" in result


class TestLLMVisionServiceBatch:
    """recognize_images_batch() 批量识别"""

    def test_empty_list(self):
        svc = LLMVisionService(api_url="https://api.example.com", api_key="key")
        result = svc.recognize_images_batch([])
        assert result == {}

    def test_all_filtered_out(self, tmp_path):
        """所有图片都被过滤掉"""
        fp = _create_small_file(tmp_path, "tiny.png")
        svc = LLMVisionService(api_url="https://api.example.com", api_key="key")
        result = svc.recognize_images_batch([fp])
        assert result == {}

    def test_batch_with_mock(self, tmp_path):
        """批量识别多张图片"""
        # Use noise images so they pass the ImageFilter
        images = []
        for i in range(3):
            fp = _create_noise_image(tmp_path, f"img{i}.png", size=(200, 200))
            images.append(fp)

        call_count = [0]

        def mock_urlopen(req, **kwargs):
            call_count[0] += 1
            return _make_mock_response(f"Description {call_count[0]}")

        # Use max_workers=1 to avoid threading issues with mock
        with patch("doc_knowledge.vision.urllib.request.urlopen", side_effect=mock_urlopen):
            svc = LLMVisionService(api_url="https://api.example.com", api_key="key", max_workers=1)
            result = svc.recognize_images_batch(images)

        assert len(result) == 3
        assert call_count[0] == 3

    def test_batch_mixed_results(self, tmp_path):
        """混合：有些图片被过滤，有些被识别"""
        good = _create_noise_image(tmp_path, "good.png", size=(200, 200))
        tiny = _create_small_file(tmp_path, "tiny.png")

        with patch("doc_knowledge.vision.urllib.request.urlopen",
                   side_effect=_mock_urlopen("Image content")):
            svc = LLMVisionService(api_url="https://api.example.com", api_key="key")
            result = svc.recognize_images_batch([good, tiny])

        assert len(result) == 1
        assert good in result

    def test_batch_verbose_output(self, tmp_path, capsys):
        """verbose=True 输出详细信息"""
        fp = _create_noise_image(tmp_path, "verbose.png", size=(200, 200))

        with patch("doc_knowledge.vision.urllib.request.urlopen",
                   side_effect=_mock_urlopen("verbose test")):
            svc = LLMVisionService(api_url="https://api.example.com", api_key="key")
            svc.recognize_images_batch([fp], verbose=True)

        captured = capsys.readouterr()
        assert "过滤完成" in captured.out or "识别完成" in captured.out

    def test_batch_with_exception(self, tmp_path):
        """批量识别中某个图片识别失败，不影响其他图片"""
        good = _create_noise_image(tmp_path, "good.png", size=(200, 200))

        call_count = [0]

        def mock_urlopen(req, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                import urllib.error
                raise urllib.error.URLError("timeout")
            return _make_mock_response("ok")

        with patch("doc_knowledge.vision.urllib.request.urlopen", side_effect=mock_urlopen):
            svc = LLMVisionService(api_url="https://api.example.com", api_key="key")
            result = svc.recognize_images_batch([good])

        assert good in result
