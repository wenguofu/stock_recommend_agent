"""组合优化 /portfolio"""
from conftest import BasePageTest


class PortfolioTest(BasePageTest):
    path = "/portfolio"
    title = "组合优化"
    interactive = [
        {"selector": "button:has-text('Markowitz')", "description": "Markowitz 优化",
         "optional": True},
        {"selector": "button:has-text('有效前沿')", "description": "有效前沿",
         "optional": True},
        {"selector": "button:has-text('风险平价')", "description": "风险平价",
         "optional": True},
    ]
