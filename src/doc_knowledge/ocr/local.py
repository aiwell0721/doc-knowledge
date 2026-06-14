"""本地 OCR 服务 — Tesseract 后端"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

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

    @staticmethod
    def _find_tesseract_cmd() -> Optional[str]:
        """跨平台查找 tesseract 可执行文件路径

        查找顺序：
        1. shutil.which("tesseract") — 优先用 PATH（覆盖 Linux/macOS/已配置 PATH 的 Windows）
        2. TESSERACT_CMD 环境变量 — 用户显式指定
        3. Windows 标准安装位置 — 通过 %ProgramFiles% 拼接，仅在文件实际存在时返回
        4. None — 都没找到，由 pytesseract 用自己的默认值
        """
        path = shutil.which("tesseract")
        if path:
            return path
        env_cmd = os.environ.get("TESSERACT_CMD")
        if env_cmd:
            return env_cmd
        if os.name == "nt":
            program_files = os.environ.get("ProgramFiles", "")
            if program_files:
                candidate = os.path.join(program_files, "Tesseract-OCR", "tesseract.exe")
                if os.path.isfile(candidate):
                    return candidate
        return None

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

            tesseract_cmd = self._find_tesseract_cmd()
            if tesseract_cmd:
                pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

            # 确保 TESSDATA_PREFIX 指向包含 .traineddata 的目录
            if "TESSDATA_PREFIX" not in os.environ:
                default_tessdata = os.path.expanduser("~/.doc-knowledge/tessdata")
                if os.path.isdir(default_tessdata):
                    os.environ["TESSDATA_PREFIX"] = default_tessdata

            img = Image.open(image_path)
            text = pytesseract.image_to_string(
                img, lang=self.lang, config="--psm 6"
            )
            return text.strip()

        except ImportError:
            return "[pytesseract 未安装，请运行: pip install pytesseract]"
        except Exception:
            # 尝试用 subprocess 直接调用 tesseract
            return self._fallback_tesseract(image_path)

    def _fallback_tesseract(self, image_path: Path) -> str:
        """pytesseract 失败时的 CLI 回退方案"""
        tesseract_cmd = self._find_tesseract_cmd()
        if not tesseract_cmd:
            return "[本地 OCR 失败: 未找到 tesseract 可执行文件，请安装 tesseract 或设置 TESSERACT_CMD 环境变量]"

        try:
            output = subprocess.run(
                [tesseract_cmd, str(image_path), "stdout", "-l", self.lang, "--psm", "6"],
                capture_output=True, text=True, timeout=30,
            )
            return output.stdout.strip()
        except Exception as e:
            return f"[本地 OCR 失败: {e}]"
