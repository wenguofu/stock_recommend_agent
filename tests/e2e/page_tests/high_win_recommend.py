"""高胜率推荐 /high-win-recommend"""
from conftest import BasePageTest


class HighWinRecommendTest(BasePageTest):
    path = "/high-win-recommend"
    title = "高胜率推荐"
    interactive = [
        {"description": "卡片/表格", "action": "wait",
         "wait_for": ".ant-card, .ant-table, .ant-empty"},
    ]
