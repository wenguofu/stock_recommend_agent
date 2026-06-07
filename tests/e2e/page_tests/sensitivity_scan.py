"""敏感度扫描 /sensitivity"""
from conftest import BasePageTest


class SensitivityScanTest(BasePageTest):
    path = "/sensitivity"
    title = "敏感度扫描"
    interactive = [
        {"selector": "button:has-text('开始扫描')", "description": "开始扫描按钮",
         "optional": True},
        {"selector": "button:has-text('编辑网格')", "description": "编辑参数网格",
         "optional": True},
    ]
