"""TDD Red — /api/valuation/dcf/<code> 路由测试

Spec Scenario spec.md:24-42:
  - 默认参数 growth=0.15 discount=0.10 terminal=0.03
  - EPS≤0 或 discount≤terminal → 返回 {error: ...}
"""
import pytest


def test_dcf_route_default_params():
    """无 query → 用默认参数, 返回 {fair_value, current_price, upside_pct}"""
    from api_routes import register_routes
    from flask import Flask

    app = Flask(__name__)
    register_routes(app)
    client = app.test_client()

    import api_routes as _api
    import unittest.mock as mock

    fake_realtime = {"code": "000001", "price": 10.0, "eps": 1.0}
    with mock.patch.object(_api, "get_realtime_data", return_value=fake_realtime):
        resp = client.get("/api/valuation/dcf/000001")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "fair_value_per_share" in data
        assert "upside_pct" in data
        assert "assumptions" in data


def test_dcf_route_custom_params():
    """?growth=0.20&discount=0.12&terminal=0.04 → assumptions 应回显"""
    from api_routes import register_routes
    from flask import Flask

    app = Flask(__name__)
    register_routes(app)
    client = app.test_client()

    import api_routes as _api
    import unittest.mock as mock

    fake_realtime = {"code": "000001", "price": 10.0, "eps": 1.0}
    with mock.patch.object(_api, "get_realtime_data", return_value=fake_realtime):
        resp = client.get("/api/valuation/dcf/000001?growth=0.20&discount=0.12&terminal=0.04")
        data = resp.get_json()
        assert data["assumptions"]["growth"] == 0.20
        assert data["assumptions"]["discount"] == 0.12
        assert data["assumptions"]["terminal"] == 0.04


def test_dcf_route_returns_error_when_eps_le_zero():
    """EPS=0 → 返回 {error: ...} (Spec Scenario spec.md:39-42)"""
    from api_routes import register_routes
    from flask import Flask

    app = Flask(__name__)
    register_routes(app)
    client = app.test_client()

    import api_routes as _api
    import unittest.mock as mock

    fake_realtime = {"code": "000001", "price": 10.0, "eps": 0.0}
    with mock.patch.object(_api, "get_realtime_data", return_value=fake_realtime):
        resp = client.get("/api/valuation/dcf/000001")
        data = resp.get_json()
        assert "error" in data


def test_dcf_route_returns_error_when_discount_le_terminal():
    """discount=0.03, terminal=0.03 → 返回 {error: ...}"""
    from api_routes import register_routes
    from flask import Flask

    app = Flask(__name__)
    register_routes(app)
    client = app.test_client()

    import api_routes as _api
    import unittest.mock as mock

    fake_realtime = {"code": "000001", "price": 10.0, "eps": 1.0}
    with mock.patch.object(_api, "get_realtime_data", return_value=fake_realtime):
        resp = client.get("/api/valuation/dcf/000001?growth=0.15&discount=0.03&terminal=0.03")
        data = resp.get_json()
        assert "error" in data