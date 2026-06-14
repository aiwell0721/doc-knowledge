"""OCR 服务抽象基类"""

from abc import ABC, abstractmethod
from pathlib import Path


class OCRService(ABC):
    """OCR 服务抽象基类 — 所有 OCR 后端的统一接口"""

    @abstractmethod
    def recognize_batch(
        self, image_paths: list[Path], verbose: bool = False
    ) -> dict[Path, str]:
        """批量识别图片，返回 {path: text} 映射"""
        ...
