"""策略库 /strategies"""
from conftest import BasePageTest


class StrategyLibraryTest(BasePageTest):
    path = "/strategies"
    title = "策略库"
    interactive = [
        {"selector": ".ant-card", "description": "策略卡片", "optional": True},
        {"selector": "a[href*='/strategies/'][href*='/run']", "description": "运行策略链接",
         "optional": True},
    ]
