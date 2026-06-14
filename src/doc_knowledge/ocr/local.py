"""本地 OCR 服务 — Tesseract 后端"""

import os
import subprocess
from pathlib import Path

from doc_knowledge.ocr.base import OCRService


class LocalOCRService(OCRService):
    """本地 OCR 识别（Tesseract）"""

    def __init__(self, engine: str = "tesseract", lang: str = "chi_sim+eng"):
        if engine != "tesseract":
            raise NotImplementedError(
                f"PaddleOCR 暂不支持（当前环境 Python 3.14 ARM64）。"
                f"请使用 engine='tesseract'。"
            )
        self.engine = engine
        self.lang = lang

    def recognize_batch(
        self, image_paths: list[Path], verbose: bool = False
    ) -> dict[Path, str]:
        results = {}
        for path in image_paths:
            results[path] = self._recognize_one(path)
        return results

    def _recognize_one(self, image_path: Path) -> str:
        if not image_path.exists():
            return f"[文件不存在: {image_path.name}]"

        try:
            from PIL import Image
            import pytesseract

            tesseract_cmd = os.environ.get(
                "TESSERACT_CMD",
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            )
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

            # 确保 TESSDATA_PREFIX 指向包含 .traineddata 的目录
            if "TESSDATA_PREFIX" not in os.environ:
                default_tessdata = os.path.expanduser(r"~\.doc-knowledge\tessdata")
                if os.path.isdir(default_tessdata):
                    os.environ["TESSDATA_PREFIX"] = default_tessdata

            img = Image.open(image_path)
            text = pytesseract.image_to_string(
                img, lang=self.lang, config="--psm 6"
            )
            return text.strip()

        except ImportError:
            return "[pytesseract 未安装，请运行: pip install pytesseract]"
        except Exception as e:
            # 尝试用 subprocess 直接调用 tesseract
            return self._fallback_tesseract(image_path)

    def _fallback_tesseract(self, image_path: Path) -> str:
        """pytesseract 失败时的 CLI 回退方案"""
        try:
            tesseract_cmd = os.environ.get(
                "TESSERACT_CMD",
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            )
            output = subprocess.run(
                [tesseract_cmd, str(image_path), "stdout", "-l", self.lang, "--psm", "6"],
                capture_output=True, text=True, timeout=30,
            )
            return output.stdout.strip()
        except Exception as e:
            return f"[本地 OCR 失败: {e}]"
