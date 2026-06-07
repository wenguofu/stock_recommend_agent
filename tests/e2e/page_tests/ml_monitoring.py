"""ML 监控 /monitoring"""
from conftest import BasePageTest


class MLMonitoringTest(BasePageTest):
    path = "/monitoring"
    title = "ML 监控"
    interactive = [
        {"selector": ".ant-tabs-tab", "description": "Tab 切换 (指标/影子/版本)",
         "optional": True, "wait_for": 0.5},
        {"selector": "button:has-text('刷新')", "description": "刷新按钮",
         "optional": True},
    ]
