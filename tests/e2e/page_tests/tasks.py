"""任务 /tasks"""
from conftest import BasePageTest


class TasksTest(BasePageTest):
    path = "/tasks"
    title = "任务"
    interactive = [
        {"selector": "button:has-text('新建')", "description": "新建任务", "optional": True},
        {"selector": "button:has-text('执行')", "description": "执行任务", "optional": True},
        {"description": "任务列表卡片", "action": "wait",
         "wait_for": ".ant-card, .ant-table, .ant-list"},
    ]
