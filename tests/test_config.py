"""配置加载模块测试"""
import os
import tempfile
from pathlib import Path

import pytest
import yaml

from doc_knowledge.config import Config, OCRConfig, load_config


class TestConfigDefaults:
    """默认配置 — 无配置文件时回退"""

    def test_load_without_file_returns_defaults(self):
        cfg = load_config(config_path=Path("/nonexistent/path/config.yaml"))
        assert cfg.ocr.enabled is False
        assert cfg.ocr.mode == "cloud"

    def test_ocr_cloud_defaults(self):
        cfg = load_config(config_path=Path("/nonexistent/path/config.yaml"))
        cloud = cfg.ocr.cloud
        assert cloud.api_url == "https://api.openai.com/v1"
        assert cloud.model == "gpt-4o"
        assert cloud.max_concurrency == 5
        assert cloud.timeout == 60

    def test_ocr_local_defaults(self):
        cfg = load_config(config_path=Path("/nonexistent/path/config.yaml"))
        local = cfg.ocr.local
        assert local.engine == "tesseract"
        assert local.lang == "chi_sim+eng"
        assert local.gpu is False

    def test_ocr_hybrid_defaults(self):
        cfg = load_config(config_path=Path("/nonexistent/path/config.yaml"))
        hybrid = cfg.ocr.hybrid
        assert hybrid.confidence_threshold == 0.6
        assert hybrid.max_cloud_calls == 50
        assert hybrid.filter_min_size_kb == 10
        assert hybrid.filter_min_resolution == 100


class TestConfigFromFile:
    """从 YAML 文件加载配置"""

    def test_load_basic_config(self):
        data = {"ocr": {"enabled": True, "mode": "local"}}
        cfg = _load_from_dict(data)
        assert cfg.ocr.enabled is True
        assert cfg.ocr.mode == "local"

    def test_load_full_config(self):
        data = {
            "ocr": {
                "enabled": True,
                "mode": "hybrid",
                "cloud": {
                    "api_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                    "model": "qwen-vl-plus",
                    "max_concurrency": 3,
                },
                "local": {"engine": "tesseract", "lang": "en", "gpu": True},
                "hybrid": {"confidence_threshold": 0.8, "max_cloud_calls": 20},
            }
        }
        cfg = _load_from_dict(data)
        assert cfg.ocr.cloud.api_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
        assert cfg.ocr.cloud.model == "qwen-vl-plus"
        assert cfg.ocr.local.engine == "tesseract"
        assert cfg.ocr.hybrid.confidence_threshold == 0.8

    def test_partial_override_keeps_defaults(self):
        """只覆盖部分字段，其余保持默认"""
        data = {"ocr": {"enabled": True, "cloud": {"model": "gpt-4o-mini"}}}
        cfg = _load_from_dict(data)
        # 覆盖的
        assert cfg.ocr.cloud.model == "gpt-4o-mini"
        # 未覆盖的保持默认
        assert cfg.ocr.cloud.api_url == "https://api.openai.com/v1"
        assert cfg.ocr.cloud.max_concurrency == 5
        assert cfg.ocr.mode == "cloud"  # 默认


class TestEnvVarSubstitution:
    """${ENV_VAR} 环境变量替换"""

    def test_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("TEST_KEY", "sk-secret-12345")
        data = {"ocr": {"enabled": True, "cloud": {"api_key": "${TEST_KEY}"}}}
        cfg = _load_from_dict(data)
        assert cfg.ocr.cloud.api_key == "sk-secret-12345"

    def test_unset_env_var_keeps_placeholder(self):
        data = {"ocr": {"enabled": True, "cloud": {"api_key": "${MISSING_VAR}"}}}
        cfg = _load_from_dict(data)
        assert cfg.ocr.cloud.api_key == ""  # 未设置的环境变量返回空字符串

    def test_no_dollar_brace_passthrough(self):
        data = {"ocr": {"enabled": True, "cloud": {"api_key": "plain-key-123"}}}
        cfg = _load_from_dict(data)
        assert cfg.ocr.cloud.api_key == "plain-key-123"


class TestConfigValidation:
    """配置合法性"""

    def test_invalid_mode_falls_back_to_default(self):
        data = {"ocr": {"enabled": True, "mode": "quantum_ocr"}}
        cfg = _load_from_dict(data)
        assert cfg.ocr.mode == "cloud"  # 回退默认

    def test_disabled_mode_ignores_ocr_config(self):
        data = {"ocr": {"enabled": False, "mode": "local"}}
        cfg = _load_from_dict(data)
        assert cfg.ocr.enabled is False


def _load_from_dict(data: dict) -> Config:
    """辅助：从 dict 生成临时 YAML 文件并加载"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as f:
        yaml.dump(data, f)
        tmp_path = Path(f.name)
    try:
        return load_config(config_path=tmp_path)
    finally:
        tmp_path.unlink()
