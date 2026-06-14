"""云端 OCR 服务 — 封装 LLMVisionService"""

from pathlib import Path

from doc_knowledge.ocr.base import OCRService
from doc_knowledge.vision import LLMVisionService


class CloudOCRService(OCRService):
    """通过 OpenAI 兼容 VLM API 进行图片识别"""

    def __init__(
        self,
        api_url: str,
        api_key: str = "",
        model: str = "gpt-4o",
        max_concurrency: int = 5,
        timeout: int = 60,
    ):
        self.api_url = api_url
        self.api_key = api_key
        self.model = model
        self._vision = LLMVisionService(
            api_url=api_url,
            api_key=api_key,
            model=model,
            max_workers=max_concurrency,
            timeout=timeout,
        )

    def recognize_batch(
        self, image_paths: list[Path], verbose: bool = False
    ) -> dict[Path, str]:
        return self._vision.recognize_images_batch(image_paths, verbose=verbose)
