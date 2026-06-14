"""OCR 服务层 — 统一管道

当前已实现：cloud（VLM API）、local（Tesseract）
未实现：hybrid（混合策略，配置类已预留）
"""

from doc_knowledge.config import Config
from doc_knowledge.ocr.base import OCRService
from doc_knowledge.ocr.cloud import CloudOCRService
from doc_knowledge.ocr.local import LocalOCRService


def create_ocr_service(config: Config) -> OCRService | None:
    """根据配置创建 OCR 服务，未启用时返回 None"""
    if not config.ocr.enabled:
        return None

    mode = config.ocr.mode
    if mode == "cloud":
        cloud = config.ocr.cloud
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
    if mode == "hybrid":
        raise NotImplementedError(
            "混合 OCR 模式尚未实现，请使用 --ocr cloud 或 --ocr local"
        )
    return None
