"""
pytest 配置 — 共享 fixtures 和条件跳过
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 标记：需要完整依赖的测试
requires_flask = pytest.mark.skipif(
    not __import__("importlib").util.find_spec("flask"),
    reason="flask 未安装",
)
