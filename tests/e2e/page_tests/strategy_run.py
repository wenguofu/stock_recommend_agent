"""策略运行 /strategies/:id/run - 此处仅测试通用 path /strategies 页面是否含 'run'"""
from conftest import BasePageTest


class StrategyRunTest(BasePageTest):
    path = "/strategies/jichang/run"
    title = "策略运行"
    interactive = [
        {"selector": "button:has-text('运行')", "description": "运行按钮", "optional": True},
        {"selector": "button:has-text('开始')", "description": "开始按钮", "optional": True},
    ]
