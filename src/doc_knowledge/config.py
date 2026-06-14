"""配置加载模块

从 ~/.doc-knowledge/config.yaml 加载配置，支持 ${ENV_VAR} 替换和默认值。
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class CloudOCRConfig:
    api_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o"
    max_concurrency: int = 5
    timeout: int = 60


@dataclass
class LocalOCRConfig:
    engine: str = "tesseract"  # paddleocr | tesseract
    lang: str = "chi_sim+eng"
    gpu: bool = False


@dataclass
class HybridOCRConfig:
    confidence_threshold: float = 0.6
    max_cloud_calls: int = 50
    filter_min_size_kb: int = 10
    filter_min_resolution: int = 100


@dataclass
class OCRConfig:
    enabled: bool = False
    mode: str = "cloud"  # cloud | local | hybrid
    cloud: CloudOCRConfig = field(default_factory=CloudOCRConfig)
    local: LocalOCRConfig = field(default_factory=LocalOCRConfig)
    hybrid: HybridOCRConfig = field(default_factory=HybridOCRConfig)


@dataclass
class Config:
    ocr: OCRConfig = field(default_factory=OCRConfig)


def load_config(config_path: Optional[Path] = None) -> Config:
    """加载配置文件，文件不存在时返回默认值"""
    if config_path is None:
        config_path = Path.home() / ".doc-knowledge" / "config.yaml"

    if not config_path.exists():
        return Config()

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    raw = _resolve_env_vars(raw)
    return _build_config(raw)


def _resolve_env_vars(data: dict) -> dict:
    """递归替换字典中的 ${ENV_VAR} 占位符"""
    env_pattern = re.compile(r"^\$\{(.+)\}$")

    def _resolve(value):
        if isinstance(value, str):
            m = env_pattern.match(value)
            if m:
                return os.environ.get(m.group(1), "")
            return value
        if isinstance(value, dict):
            return {k: _resolve(v) for k, v in value.items()}
        return value

    return {k: _resolve(v) for k, v in data.items()}


def _build_config(raw: dict) -> Config:
    """从原始字典构建 Config 对象，合并默认值"""
    ocr_raw = raw.get("ocr", {})

    mode = ocr_raw.get("mode", "cloud")
    if mode not in ("cloud", "local", "hybrid"):
        mode = "cloud"

    cloud_raw = ocr_raw.get("cloud", {})
    cloud = CloudOCRConfig(
        api_url=cloud_raw.get("api_url", CloudOCRConfig.api_url),
        api_key=cloud_raw.get("api_key", CloudOCRConfig.api_key),
        model=cloud_raw.get("model", CloudOCRConfig.model),
        max_concurrency=cloud_raw.get("max_concurrency", CloudOCRConfig.max_concurrency),
        timeout=cloud_raw.get("timeout", CloudOCRConfig.timeout),
    )

    local_raw = ocr_raw.get("local", {})
    local = LocalOCRConfig(
        engine=local_raw.get("engine", LocalOCRConfig.engine),
        lang=local_raw.get("lang", LocalOCRConfig.lang),
        gpu=local_raw.get("gpu", LocalOCRConfig.gpu),
    )

    hybrid_raw = ocr_raw.get("hybrid", {})
    hybrid = HybridOCRConfig(
        confidence_threshold=hybrid_raw.get(
            "confidence_threshold", HybridOCRConfig.confidence_threshold
        ),
        max_cloud_calls=hybrid_raw.get("max_cloud_calls", HybridOCRConfig.max_cloud_calls),
        filter_min_size_kb=hybrid_raw.get(
            "filter", {}
        ).get("min_size_kb", HybridOCRConfig.filter_min_size_kb),
        filter_min_resolution=hybrid_raw.get(
            "filter", {}
        ).get("min_resolution", HybridOCRConfig.filter_min_resolution),
    )

    return Config(
        ocr=OCRConfig(
            enabled=ocr_raw.get("enabled", False),
            mode=mode,
            cloud=cloud,
            local=local,
            hybrid=hybrid,
        )
    )
