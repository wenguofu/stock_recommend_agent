"""TDD Red — /api/fundamentals/<code>/history 路由测试

Spec Scenario spec.md:9-19:
  - history 数组长度 ≥ 2 → 返回时序
  - history 数组长度 < 2 → 返回空数组 (前端走 Alert 分支)
"""
import pytest


def test_fundamentals_history_returns_list():
    """正常: 历史 ≥ 2 期时返回 list 包含 report_date + 财务字段"""
    # 用 monkeypatch 模拟 db session 避免真实 DB
    from api_routes import register_routes
    from flask import Flask

    app = Flask(__name__)
    register_routes(app)
    client = app.test_client()

    # 通过 monkeypatch get_stock_financials
    import api_routes as _api
    import unittest.mock as mock

    fake_rows = [
        {
            "code": "000001", "report_date": "2024-12-31",
            "revenue": 100.0, "net_profit": 10.0, "roe": 0.10,
            "gross_margin": 0.40, "eps": 0.5,
        },
        {
            "code": "000001", "report_date": "2023-12-31",
            "revenue": 80.0, "net_profit": 8.0, "roe": 0.09,
            "gross_margin": 0.38, "eps": 0.4,
        },
    ]
    import db as _db
    with mock.patch.object(_db, "get_stock_financials", return_value=fake_rows), \
         mock.patch.object(_api, "SessionLocal", return_value=mock.MagicMock()):
        resp = client.get("/api/fundamentals/000001/history?limit=8")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "history" in data
        assert len(data["history"]) == 2
        assert data["history"][0]["report_date"] == "2024-12-31"


def test_fundamentals_history_empty_when_lt_2():
    """无历史 → 返回 history=[]"""
    from api_routes import register_routes
    from flask import Flask

    app = Flask(__name__)
    register_routes(app)
    client = app.test_client()

    import api_routes as _api
    import unittest.mock as mock

    import db as _db
    with mock.patch.object(_db, "get_stock_financials", return_value=[]), \
         mock.patch.object(_api, "SessionLocal", return_value=mock.MagicMock()):
        resp = client.get("/api/fundamentals/999999/history?limit=8")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["history"] == []


def test_fundamentals_history_limit_query_param():
    """?limit=4 应被传递给 get_stock_financials"""
    from api_routes import register_routes
    from flask import Flask

    app = Flask(__name__)
    register_routes(app)
    client = app.test_client()

    import api_routes as _api
    import unittest.mock as mock

    mock_fn = mock.MagicMock(return_value=[])
    import db as _db
    with mock.patch.object(_db, "get_stock_financials", mock_fn), \
         mock.patch.object(_api, "SessionLocal", return_value=mock.MagicMock()):
        resp = client.get("/api/fundamentals/000001/history?limit=4")
        assert resp.status_code == 200
        assert mock_fn.called
        # 第二个位置参数应是 limit=4
        call_kwargs = mock_fn.call_args.kwargs
        call_args = mock_fn.call_args.args
        # 函数签名: get_stock_financials(db, code, limit=4)
        assert (len(call_args) >= 3 and call_args[2] == 4) or call_kwargs.get("limit") == 4