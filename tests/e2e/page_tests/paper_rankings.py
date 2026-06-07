"""收益排名 /paper/rankings"""
from conftest import BasePageTest


class PaperRankingsTest(BasePageTest):
    path = "/paper/rankings"
    title = "收益排名"
    interactive = [
        {"description": "排名表格", "action": "wait",
         "wait_for": ".ant-table, .ant-empty"},
    ]
