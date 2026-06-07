"""
测试 config.py — 环境变量优先级
"""
import os
import sys
import pytest

# 确保项目根在 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestConfig:
    """config 模块测试"""

    def test_api_base_default(self, monkeypatch):
        """默认值应为 127.0.0.1:35000"""
        monkeypatch.delenv("A_STOCK_API", raising=False)
        import config
        import importlib
        importlib.reload(config)
        assert config.API_BASE == "http://127.0.0.1:35000"

    def test_api_base_from_env(self, monkeypatch):
        """环境变量覆盖默认值"""
        monkeypatch.setenv("A_STOCK_API", "http://192.168.1.100:9000")
        import config
        import importlib
        importlib.reload(config)
        assert config.API_BASE == "http://192.168.1.100:9000"

    def test_api_port_default(self, monkeypatch):
        """默认端口 35000"""
        monkeypatch.delenv("API_PORT", raising=False)
        import config
        import importlib
        importlib.reload(config)
        assert config.API_PORT == 35000

    def test_api_port_from_env(self, monkeypatch):
        """环境变量覆盖端口"""
        monkeypatch.setenv("API_PORT", "8080")
        import config
        import importlib
        importlib.reload(config)
        assert config.API_PORT == 8080
