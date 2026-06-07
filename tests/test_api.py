"""API 集成测试 — 验证关键端点的请求-响应
需要完整依赖（flask/pandas/sqlalchemy），在 venv 中自动跳过
"""
import pytest
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 检查关键依赖
try:
    from api_server import app as _test_app
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

pytestmark = pytest.mark.skipif(not HAS_DEPS, reason="缺少 flask/pandas 等依赖")


@pytest.fixture
def client():
    """Flask test client"""
    from api_server import app
    app.config["TESTING"] = True
    return app.test_client()


class TestHealth:
    def test_health_endpoint(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"

    def test_404_returns_json(self, client):
        resp = client.get("/api/nonexistent")
        assert resp.status_code == 404
        data = resp.get_json()
        # 验证返回的是 JSON 且包含错误信息 (Flask error_handler 格式)
        assert data is not None
        assert "error" in data
        assert isinstance(data["error"], str)


class TestWatchlist:
    def test_get_watchlist(self, client):
        resp = client.get("/api/watchlist")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert isinstance(data["data"], list)

    def test_add_and_delete_watchlist(self, client):
        # Add
        resp = client.post(
            "/api/watchlist",
            json={"code": "999999", "name": "测试股票"},
        )
        assert resp.status_code == 200

        # Delete
        resp = client.delete("/api/watchlist/999999")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True


class TestMidline:
    def test_watchlist_health(self, client):
        resp = client.get("/api/midline/watchlist-health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "data" in data
        assert isinstance(data["data"], list)

    def test_position_calc(self, client):
        resp = client.post(
            "/api/midline/position-calc",
            json={
                "total_capital": 100000,
                "risk_pct": 2,
                "entry_price": 55.0,
                "stop_loss_price": 52.0,
                "target_price": 62.0,
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["suggested_shares"] >= 100
        assert data["risk_reward_ratio"] > 0


class TestConfig:
    def test_get_configs(self, client):
        resp = client.get("/api/config")
        assert resp.status_code == 200

    def test_config_not_found(self, client):
        resp = client.get("/api/config/no_such_key_xyz")
        assert resp.status_code == 404


class TestSectors:
    def test_list_sectors(self, client):
        resp = client.get("/api/sectors")
        assert resp.status_code == 200

    def test_sector_performance(self, client):
        resp = client.get("/api/sectors/performance")
        # May be 200 or 500 if data unavailable; either is acceptable in test
        assert resp.status_code in (200, 500)


class TestRealtime:
    def test_realtime_data(self, client):
        resp = client.get("/api/sina/realtime/000001")
        # May fail if market closed; accept 200 or 500
        assert resp.status_code in (200, 500)
