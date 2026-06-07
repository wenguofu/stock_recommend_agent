"""策略配置 /strategy-config"""
from conftest import BasePageTest


class StrategyConfigTest(BasePageTest):
    path = "/strategy-config"
    title = "策略配置"
    interactive = [
        {"selector": ".ant-tabs-tab", "description": "Tab 切换", "optional": True},
        {"selector": "button:has-text('保存')", "description": "保存按钮", "optional": True},
        {"selector": "button:has-text('重置')", "description": "重置按钮", "optional": True},
    ]
