"""OCR 服务层 — 统一管道

当前已实现：cloud（VLM API）、local（Tesseract）、slide（整页渲染 + 云端 VLM）
未实现：hybrid（混合策略，配置类已预留）
"""

from doc_knowledge.config import Config
from doc_knowledge.ocr.base import OCRService
from doc_knowledge.ocr.cloud import CloudOCRService
from doc_knowledge.ocr.local import LocalOCRService
from doc_knowledge.ocr.slide import SlideFusionService


def create_ocr_service(config: Config) -> OCRService | SlideFusionService | None:
    """根据配置创建 OCR 服务，未启用时返回 None

    返回两种接口之一：
    - OCRService（图像级）：cloud / local / hybrid（未实现）
    - SlideFusionService（页面级）：slide
    """
    if not config.ocr.enabled:
        return None

    mode = config.ocr.mode
    cloud = config.ocr.cloud
    if mode == "cloud":
        return CloudOCRService(
            api_url=cloud.api_url,
            api_key=cloud.api_key,
            model=cloud.model,
            max_concurrency=cloud.max_concurrency,
            timeout=cloud.timeout,
        )
    if mode == "local":
        local = config.ocr.local
        return LocalOCRService(engine=local.engine, lang=local.lang)
    if mode == "slide":
        slide = config.ocr.slide
        return SlideFusionService(
            api_url=cloud.api_url,
            api_key=cloud.api_key,
            model=cloud.model,
            dpi=slide.dpi,
            prompt=slide.prompt or None,
            # 并发走 slide.max_concurrency（默认 1=串行）而非 cloud.max_concurrency：
            # 免费 VLM（glm-4.6v-flash）并发限流，需要并发的付费模型自行调配置。
            max_concurrency=slide.max_concurrency,
            timeout=cloud.timeout,
            libreoffice_path=slide.libreoffice_path,
        )
    if mode == "hybrid":
        raise NotImplementedError(
            "混合 OCR 模式尚未实现，请使用 --ocr cloud 或 --ocr local"
        )
    return None
