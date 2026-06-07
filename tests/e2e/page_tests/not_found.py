"""404 页面 /nonexistent"""
from conftest import BasePageTest


class NotFoundTest(BasePageTest):
    path = "/nonexistent-route-12345"
    title = "404"
    # 此页是反向测试: 应当显示 404
