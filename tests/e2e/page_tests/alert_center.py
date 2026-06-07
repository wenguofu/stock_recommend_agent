"""告警中心 /alerts"""
from conftest import BasePageTest


class AlertCenterTest(BasePageTest):
    path = "/alerts"
    title = "告警中心"
    interactive = [
        {"selector": "button:has-text('发送')", "description": "发送告警", "optional": True},
        {"selector": "button:has-text('清空')", "description": "清空缓存", "optional": True},
    ]
