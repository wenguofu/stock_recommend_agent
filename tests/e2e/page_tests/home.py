"""首页 / - 行情总览 + 推荐 + 板块 + 大盘"""
from conftest import BasePageTest


class HomeTest(BasePageTest):
    path = "/"
    title = "首页"
    interactive = [
        {"selector": ".ant-card", "description": "首页卡片存在", "optional": True, "wait_for": 0.5},
    ]
