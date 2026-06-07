"""策略推荐 /strategy"""
from conftest import BasePageTest


class StrategyRecommendTest(BasePageTest):
    path = "/strategy"
    title = "策略推荐"
    interactive = [
        {"selector": "button:has-text('添加')", "description": "添加自选", "optional": True},
        {"selector": "button:has-text('创建')", "description": "创建计划", "optional": True},
    ]
