"""模拟盘盈亏分解 /paper/breakdown/:id"""
from conftest import BasePageTest


class PaperBreakdownTest(BasePageTest):
    path = "/paper/breakdown/1"
    title = "盈亏分解"
    interactive = [
        {"selector": ".ant-card", "description": "卡片", "optional": True},
    ]
