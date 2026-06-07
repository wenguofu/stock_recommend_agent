"""模拟盘详情 /paper/:id"""
from conftest import BasePageTest


class PaperDetailTest(BasePageTest):
    path = "/paper/1"
    title = "模拟盘详情"
    interactive = [
        {"selector": "button:has-text('下单')", "description": "下单按钮", "optional": True},
        {"selector": ".ant-tabs", "description": "Tab 存在", "optional": True},
    ]
