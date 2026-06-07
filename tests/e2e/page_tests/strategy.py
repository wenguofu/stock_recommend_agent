"""策略 /strategy"""
from conftest import BasePageTest


class StrategyTest(BasePageTest):
    path = "/strategy"
    title = "策略"
    interactive = [
        {"selector": "button:has-text('批量')", "description": "批量操作", "optional": True},
        {"selector": "button:has-text('辩论')", "description": "启动辩论", "optional": True},
    ]
