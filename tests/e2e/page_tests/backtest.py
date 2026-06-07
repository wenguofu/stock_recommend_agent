"""回测 /backtest"""
from conftest import BasePageTest


class BacktestTest(BasePageTest):
    path = "/backtest"
    title = "回测"
    interactive = [
        {"selector": "button:has-text('运行')", "description": "运行回测", "optional": True},
        {"selector": "button:has-text('开始')", "description": "开始回测", "optional": True},
        {"selector": ".ant-select", "description": "策略下拉", "optional": True},
    ]
