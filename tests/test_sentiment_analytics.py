"""TDD Red — /api/sentiment/analytics/<code> 合并路由测试

Spec Scenario spec.md:81-110:
  - 返回 {index, keywords, news}
  - index 数组每项 {date, score, count}
  - keywords 数组按 count desc
  - news 数组日期窗口 ≤ days
"""
import pytest


def test_sentiment_analytics_returns_combined_payload():
    """正常路径: 返回 {index, keywords, news} 3 个字段"""
    from api_routes import register_routes
    from flask import Flask

    app = Flask(__name__)
    register_routes(app)
    client = app.test_client()

    import api_routes as _api
    import unittest.mock as mock

    fake_news = [
        {"date": "2025-01-01", "title": "业绩利好", "source": "新浪"},
    ]
    fake_posts = [
        {"date": "2025-01-01", "title": "增长超预期", "source": "guba"},
    ]
    with mock.patch.object(_api, "get_news_from_stock", return_value=fake_news), \
         mock.patch.object(_api, "get_guba_posts", return_value=fake_posts):
        resp = client.get("/api/sentiment/analytics/000001?days=30&top=20")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "index" in data
        assert "keywords" in data
        assert "news" in data
        assert isinstance(data["index"], list)
        assert isinstance(data["keywords"], list)
        assert isinstance(data["news"], list)


def test_sentiment_analytics_empty_data_still_returns_shape():
    """无新闻/帖子 → 仍返回 3 个空字段"""
    from api_routes import register_routes
    from flask import Flask

    app = Flask(__name__)
    register_routes(app)
    client = app.test_client()

    import api_routes as _api
    import unittest.mock as mock

    with mock.patch.object(_api, "get_news_from_stock", return_value=[]), \
         mock.patch.object(_api, "get_guba_posts", return_value=[]):
        resp = client.get("/api/sentiment/analytics/000001?days=30&top=20")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["index"] == []
        assert data["keywords"] == []
        assert data["news"] == []


def test_sentiment_analytics_default_params():
    """不带 query 应使用默认值 days=30 top=20"""
    from api_routes import register_routes
    from flask import Flask

    app = Flask(__name__)
    register_routes(app)
    client = app.test_client()

    import api_routes as _api
    import unittest.mock as mock

    news_mock = mock.MagicMock(return_value=[])
    posts_mock = mock.MagicMock(return_value=[])
    with mock.patch.object(_api, "get_news_from_stock", news_mock), \
         mock.patch.object(_api, "get_guba_posts", posts_mock):
        resp = client.get("/api/sentiment/analytics/000001")
        assert resp.status_code == 200