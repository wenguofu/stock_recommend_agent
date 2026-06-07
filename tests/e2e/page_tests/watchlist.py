"""自选股 /watchlist"""
from conftest import BasePageTest


class WatchlistTest(BasePageTest):
    path = "/watchlist"
    title = "自选股"
    interactive = [
        {"selector": "button:has-text('添加')", "description": "添加按钮", "optional": True},
        {"description": "表格或空状态", "action": "wait",
         "wait_for": ".ant-table, .ant-empty"},
    ]
