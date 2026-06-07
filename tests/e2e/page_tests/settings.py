"""系统配置 /settings"""
from conftest import BasePageTest


class SettingsTest(BasePageTest):
    path = "/settings"
    title = "系统配置"
    interactive = [
        {"selector": "button:has-text('保存')", "description": "保存配置", "optional": True},
        {"selector": "button:has-text('测试')", "description": "测试 AI 连接", "optional": True},
    ]
