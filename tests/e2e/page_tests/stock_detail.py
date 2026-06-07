"""个股详情 /stock/:code"""
from conftest import BasePageTest


class StockDetailTest(BasePageTest):
    path = "/stock/000001"
    title = "个股详情"
    interactive = [
        {"selector": ".ant-tabs-tab", "description": "Tab 切换", "optional": True},
        {"selector": "h1, h2, h3, .ant-typography", "description": "标题存在"},
        # Sprint 6 优化: 估值 Tab
        {"selector": ".ant-tabs-tab:has-text('估值')", "description": "估值Tab", "optional": True},
    ]
