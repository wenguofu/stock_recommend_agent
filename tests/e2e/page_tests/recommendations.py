"""股票推荐 /recommendations"""
from conftest import BasePageTest


class RecommendationsTest(BasePageTest):
    path = "/recommendations"
    title = "股票推荐"
    interactive = [
        {"description": "列表/卡片", "action": "wait",
         "wait_for": ".ant-card, .ant-table, .ant-list, .ant-empty"},
    ]
