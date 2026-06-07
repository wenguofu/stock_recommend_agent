"""AI 辩论 /ai-debate"""
from conftest import BasePageTest


class AIDebateTest(BasePageTest):
    path = "/ai-debate"
    title = "AI 辩论"
    interactive = [
        {"selector": "button:has-text('启动')", "description": "启动辩论", "optional": True},
        {"selector": "button:has-text('开始')", "description": "开始", "optional": True},
        {"selector": ".ant-tabs", "description": "Tab 存在", "optional": True},
    ]
