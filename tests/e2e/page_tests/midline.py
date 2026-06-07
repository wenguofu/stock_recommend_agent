"""自选池健康度 /midline"""
from conftest import BasePageTest


class MidlineTest(BasePageTest):
    path = "/midline"
    title = "自选池健康度"
    interactive = [
        {"description": "卡片/表格", "action": "wait",
         "wait_for": ".ant-card, .ant-table, .ant-empty"},
    ]
