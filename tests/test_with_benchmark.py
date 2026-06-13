"""TDD Red — /api/sina/daily/with_benchmark/<code> 路由测试

Spec Scenario spec.md:47-71:
  - 返回 {stock, benchmark, patterns, benchmark_field, count}
  - patterns 5 类: gap_up / gap_down / doji / upper_shadow / lower_shadow
"""
import pytest


def test_with_benchmark_returns_combined_payload():
    from api_routes import register_routes
    from flask import Flask

    app = Flask(__name__)
    register_routes(app)
    client = app.test_client()

    import api_routes as _api
    import unittest.mock as mock

    fake_stock = [
        {"date": "2025-01-01", "open": 10, "high": 10.5, "low": 9.5, "close": 10.2},
        {"date": "2025-01-02", "open": 11.0, "high": 11.5, "low": 10.8, "close": 11.3},  # 跳空向上
    ]
    fake_bench = [
        {"date": "2025-01-01", "open": 3000, "high": 3010, "low": 2995, "close": 3005},
        {"date": "2025-01-02", "open": 3010, "high": 3020, "low": 3000, "close": 3015},
    ]

    def fake_get_daily_kline(code, count=240):
        return fake_stock if code != "sh000300" else fake_bench

    with mock.patch.object(_api, "get_daily_kline", side_effect=fake_get_daily_kline):
        resp = client.get("/api/sina/daily/with_benchmark/000001?index=sh000300&count=240")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "stock" in data
        assert "benchmark" in data
        assert "patterns" in data
        assert data["benchmark_field"] == "sh000300"
        assert isinstance(data["patterns"], list)


def test_with_benchmark_patterns_include_gap_up():
    from api_routes import register_routes
    from flask import Flask

    app = Flask(__name__)
    register_routes(app)
    client = app.test_client()

    import api_routes as _api
    import unittest.mock as mock

    fake_stock = [
        {"date": "2025-01-01", "open": 10.0, "high": 10.5, "low": 9.5, "close": 10.2},
        {"date": "2025-01-02", "open": 11.0, "high": 11.5, "low": 10.8, "close": 11.3},
    ]

    def fake_get_daily_kline(code, count=240):
        return fake_stock if code != "sh000300" else []

    with mock.patch.object(_api, "get_daily_kline", side_effect=fake_get_daily_kline):
        resp = client.get("/api/sina/daily/with_benchmark/000001")
        data = resp.get_json()
        types = [p["type"] for p in data["patterns"]]
        assert "gap_up" in types


def test_with_benchmark_empty_stock_returns_empty_patterns():
    from api_routes import register_routes
    from flask import Flask

    app = Flask(__name__)
    register_routes(app)
    client = app.test_client()

    import api_routes as _api
    import unittest.mock as mock

    with mock.patch.object(_api, "get_daily_kline", return_value=[]):
        resp = client.get("/api/sina/daily/with_benchmark/000001")
        data = resp.get_json()
        assert data["stock"] == []
        assert data["patterns"] == []