"""模拟盘 /paper"""
from conftest import BasePageTest


class PaperAccountsTest(BasePageTest):
    path = "/paper"
    title = "模拟盘"
    interactive = [
        {"selector": "button:has-text('新建')", "description": "新建账户", "optional": True},
        {"description": "账户内容", "action": "wait",
         "wait_for": ".ant-card, .ant-table, .ant-list, .ant-empty"},
    ]
