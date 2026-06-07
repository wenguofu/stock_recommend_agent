"""
Sprint 6: 估值功能 — 机构预测自动填充单元测试

覆盖:
  - _parse_yi_value 解析 "1.2亿"/"125.3 亿"/"-0.5"/""/None
  - get_institutional_forecast 表不存在 → None
  - auto_fill_institutional_forecast:
      * 无 DB 数据 + 无用户输入 → source="none"
      * 无 DB 数据 + 用户输入 → source="user"
      * 有 DB 数据 + 无用户输入 → 自动计算增速, source="institutional"
      * 有 DB 数据 + 用户输入 → 保留用户值, source="user"
  - quick_valuation 返回 forecast 元数据
"""
import os
import sys
from unittest.mock import patch, MagicMock
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

import pytest


@pytest.fixture
def fresh_quant_valuation():
    """强制重载 quant_valuation, 避免 .pyc 缓存污染"""
    for mod in list(sys.modules.keys()):
        if mod in ('quant_valuation', 'valuation_routes'):
            del sys.modules[mod]
    import quant_valuation
    return quant_valuation


# ── _parse_yi_value 解析 ──────────────────────────────

class TestParseYiValue:

    def test_simple_value(self, fresh_quant_valuation):
        assert fresh_quant_valuation._parse_yi_value("1.2亿") == 1.2

    def test_with_space(self, fresh_quant_valuation):
        assert fresh_quant_valuation._parse_yi_value("125.3 亿") == 125.3

    def test_negative(self, fresh_quant_valuation):
        assert fresh_quant_valuation._parse_yi_value("-0.5") == -0.5

    def test_empty_string(self, fresh_quant_valuation):
        assert fresh_quant_valuation._parse_yi_value("") == 0.0

    def test_none(self, fresh_quant_valuation):
        assert fresh_quant_valuation._parse_yi_value(None) == 0.0

    def test_pure_number(self, fresh_quant_valuation):
        assert fresh_quant_valuation._parse_yi_value(3.14) == 3.14

    def test_int(self, fresh_quant_valuation):
        assert fresh_quant_valuation._parse_yi_value(100) == 100.0


# ── get_institutional_forecast ──────────────────────────

class TestGetInstitutionalForecast:

    def test_no_table_returns_none(self, fresh_quant_valuation):
        """prediction_aggregates 表不存在 (SQLite 默认), 应返回 None 而不抛异常"""
        result = fresh_quant_valuation.get_institutional_forecast('999999')
        assert result is None

    def test_empty_table_returns_none(self, fresh_quant_valuation, tmp_path):
        """表存在但无数据, 返回 None"""
        # get_db 在函数内部 import, 通过 patch sys.modules['models'] 拦截
        from sqlalchemy.exc import OperationalError
        mock_models = MagicMock()
        mock_models.get_db.return_value.__next__.return_value.execute.side_effect = \
            OperationalError("SELECT", {}, Exception("no such table"))
        with patch.dict(sys.modules, {'models': mock_models}):
            result = fresh_quant_valuation.get_institutional_forecast('999999')
        assert result is None

    def test_with_data(self, fresh_quant_valuation):
        """有数据时解析 net_profit_* 字段并返回结构化 dict"""
        mock_row = MagicMock()
        mock_row._mapping = {
            'net_profit_2025a': '5亿',
            'net_profit_2026e': '10亿',
            'net_profit_2027e': '15亿',
            'net_profit_2028e': '',
            'eps_2025a': '',
            'eps_2026e': '1.5',
            'eps_2027e': '2.25',
            'eps_2028e': '',
            'rating_label': '强烈推荐',
            'analyst_count': '12',
            'updated_at': '2026-06-01',
        }
        mock_models = MagicMock()
        mock_models.get_db.return_value.__next__.return_value.execute.return_value.fetchone.return_value = mock_row
        with patch.dict(sys.modules, {'models': mock_models}):
            result = fresh_quant_valuation.get_institutional_forecast('002916')

        assert result is not None
        assert result['has_data'] is True
        assert result['net_profit_2025a'] == 5.0
        assert result['net_profit_2026e'] == 10.0
        assert result['net_profit_2027e'] == 15.0
        assert result['eps_2026e'] == 1.5
        assert result['analyst_count'] == 12
        assert result['rating_label'] == '强烈推荐'

    def test_with_datetime_updated_at(self, fresh_quant_valuation):
        """回归测试: updated_at 为 datetime 对象时不应崩溃 (信维通信 300136 真实数据)

        Bug: 'datetime.datetime' object has no attribute 'strip'
        """
        import datetime
        mock_row = MagicMock()
        mock_row._mapping = {
            'net_profit_2025a': '7.09亿',
            'net_profit_2026e': '10.69亿',
            'net_profit_2027e': '14.70亿',
            'net_profit_2028e': '26.96亿',
            'eps_2025a': '0.73',
            'eps_2026e': '1.11',
            'eps_2027e': '1.52',
            'eps_2028e': '2.79',
            'rating_label': '买入',
            'analyst_count': '8',
            'updated_at': datetime.datetime(2026, 6, 1, 23, 2, 48),  # 真实: datetime 对象
        }
        mock_models = MagicMock()
        mock_models.get_db.return_value.__next__.return_value.execute.return_value.fetchone.return_value = mock_row
        with patch.dict(sys.modules, {'models': mock_models}):
            result = fresh_quant_valuation.get_institutional_forecast('300136')

        assert result is not None
        assert result['has_data'] is True
        assert result['net_profit_2025a'] == 7.09
        assert result['net_profit_2026e'] == 10.69
        # updated_at 必须是字符串 (前端展示)
        assert isinstance(result['updated_at'], str)
        assert '2026-06-01' in result['updated_at']
        assert result['analyst_count'] == 8
        assert result['rating_label'] == '买入'


# ── auto_fill_institutional_forecast ──────────────────────

class TestAutoFillForecast:

    def test_no_data_no_user_input(self, fresh_quant_valuation):
        """无 DB 数据 + 无用户输入 → source='none'"""
        with patch.object(fresh_quant_valuation, 'get_institutional_forecast', return_value=None):
            inp = fresh_quant_valuation.ValuationInput(code='999999')
            inp = fresh_quant_valuation.auto_fill_institutional_forecast(inp)
            assert inp.forecast_source == "none"
            assert inp.industry_growth_6m == 0
            assert inp.industry_growth_1y == 0

    def test_no_data_with_user_input(self, fresh_quant_valuation):
        """无 DB 数据 + 用户输入 → source='user'"""
        with patch.object(fresh_quant_valuation, 'get_institutional_forecast', return_value=None):
            inp = fresh_quant_valuation.ValuationInput(
                code='999999',
                industry_growth_6m=100,
                industry_growth_1y=200,
            )
            inp = fresh_quant_valuation.auto_fill_institutional_forecast(inp)
            assert inp.forecast_source == "user"
            assert inp.industry_growth_6m == 100  # 保留
            assert inp.industry_growth_1y == 200  # 保留

    def test_with_data_no_user_input(self, fresh_quant_valuation):
        """有 DB 数据 + 无用户输入 → 自动计算增速, source='institutional'

        数据: 2025A=5亿, 2026E=10亿 (翻倍), 2027E=15亿
        预期: growth_6m = (10-5)/5*100 = 100%
              growth_1y = (sqrt(15/5) - 1)*100 = ~73.21%
        """
        mock_fc = {
            'net_profit_2025a': 5.0,
            'net_profit_2026e': 10.0,
            'net_profit_2027e': 15.0,
            'eps_2026e': 1.5,
            'eps_2027e': 2.25,
            'analyst_count': 12,
            'rating_label': '强烈推荐',
            'updated_at': '2026-06-01',
            'has_data': True,
        }
        with patch.object(fresh_quant_valuation, 'get_institutional_forecast', return_value=mock_fc):
            inp = fresh_quant_valuation.ValuationInput(code='002916')
            inp = fresh_quant_valuation.auto_fill_institutional_forecast(inp)

            assert inp.forecast_source == "institutional"
            assert abs(inp.industry_growth_6m - 100.0) < 0.01
            assert abs(inp.industry_growth_1y - 73.21) < 0.01
            assert inp.forecast_analyst_count == 12
            assert inp.forecast_rating_label == "强烈推荐"
            assert inp.forecast_net_profit_2025a == 5.0
            assert inp.forecast_net_profit_2026e == 10.0

    def test_with_data_user_overrides(self, fresh_quant_valuation):
        """有 DB 数据 + 用户输入 → 保留用户值, source='user'"""
        mock_fc = {
            'net_profit_2025a': 5.0,
            'net_profit_2026e': 10.0,
            'net_profit_2027e': 15.0,
            'eps_2026e': 1.5,
            'eps_2027e': 2.25,
            'analyst_count': 12,
            'rating_label': '强烈推荐',
            'updated_at': '2026-06-01',
            'has_data': True,
        }
        with patch.object(fresh_quant_valuation, 'get_institutional_forecast', return_value=mock_fc):
            inp = fresh_quant_valuation.ValuationInput(
                code='002916',
                industry_growth_6m=200,  # 用户强制 200%
                industry_growth_1y=300,
            )
            inp = fresh_quant_valuation.auto_fill_institutional_forecast(inp)

            assert inp.forecast_source == "user"
            assert inp.industry_growth_6m == 200  # 用户值保留
            assert inp.industry_growth_1y == 300
            # 但 metadata 仍记录
            assert inp.forecast_analyst_count == 12

    def test_with_data_no_2027(self, fresh_quant_valuation):
        """有数据但缺 2027E → 1y 用 2026E 同比代替"""
        mock_fc = {
            'net_profit_2025a': 5.0,
            'net_profit_2026e': 10.0,
            'net_profit_2027e': 0,  # 缺
            'eps_2026e': 1.5,
            'eps_2027e': 0,
            'analyst_count': 5,
            'rating_label': '推荐',
            'updated_at': '',
            'has_data': True,
        }
        with patch.object(fresh_quant_valuation, 'get_institutional_forecast', return_value=mock_fc):
            inp = fresh_quant_valuation.ValuationInput(code='002916')
            inp = fresh_quant_valuation.auto_fill_institutional_forecast(inp)
            assert inp.forecast_source == "institutional"
            assert abs(inp.industry_growth_6m - 100.0) < 0.01
            assert abs(inp.industry_growth_1y - 100.0) < 0.01  # 用 6m 代替


# ── quick_valuation 返回值结构 ──────────────────────────

class TestQuickValuationReturnsForecast:

    def test_forecast_field_present(self, fresh_quant_valuation):
        """quick_valuation 返回 dict 必须包含 forecast 字段"""
        with patch.object(fresh_quant_valuation, 'get_institutional_forecast', return_value=None):
            with patch.object(fresh_quant_valuation, 'auto_fill_institutional_forecast',
                              side_effect=lambda x: x):
                with patch('data_fetchers.get_realtime_data', return_value=None):
                    result = fresh_quant_valuation.quick_valuation(
                        code='002916', industry_growth_6m=50, industry_growth_1y=100,
                    )

        assert 'forecast' in result
        assert result['forecast']['source'] == "none"
        assert result['forecast']['has_data'] is False
        assert result['forecast']['growth_6m_implied'] == 50
        assert result['forecast']['growth_1y_implied'] == 100

    def test_forecast_with_data(self, fresh_quant_valuation):
        """有机构预测时, quick_valuation 返回 institutional 元数据"""
        mock_fc = {
            'net_profit_2025a': 5.0,
            'net_profit_2026e': 10.0,
            'net_profit_2027e': 15.0,
            'eps_2026e': 1.5,
            'eps_2027e': 2.25,
            'analyst_count': 12,
            'rating_label': '强烈推荐',
            'updated_at': '2026-06-01',
            'has_data': True,
        }
        with patch.object(fresh_quant_valuation, 'get_institutional_forecast', return_value=mock_fc):
            with patch('data_fetchers.get_realtime_data', return_value=None):
                result = fresh_quant_valuation.quick_valuation(
                    code='002916', industry_growth_6m=0, industry_growth_1y=0,
                )

        assert result['forecast']['source'] == "institutional"
        assert result['forecast']['has_data'] is True
        assert result['forecast']['net_profit_2026e'] == 10.0
        assert result['forecast']['analyst_count'] == 12
        assert result['forecast']['rating_label'] == "强烈推荐"
        # 增速已被自动填充
        assert abs(result['forecast']['growth_6m_implied'] - 100.0) < 0.01


# ── 估值路由集成测试 ──────────────────────────────────

class TestValuationRoutes:
    """测试估值 API 端点"""

    @pytest.fixture
    def client(self, fresh_quant_valuation):
        from flask import Flask
        from valuation_routes import register_valuation_routes
        app = Flask(__name__)
        app.config['TESTING'] = True
        register_valuation_routes(app)
        return app.test_client()

    def test_forecast_endpoint_no_data(self, client):
        """GET /api/valuation/forecast/<code> 无数据时返回 has_data=false"""
        r = client.get('/api/valuation/forecast/999999')
        assert r.status_code == 200
        body = r.get_json()
        assert body['success'] is True
        assert body['data']['has_data'] is False
        assert body['data']['source'] == 'none'

    def test_quick_endpoint_with_user_input(self, client):
        """POST /api/valuation/quick 用户输入时, source='user'"""
        r = client.post('/api/valuation/quick', json={
            'code': '999999',
            'industry_growth_6m': 100,
            'industry_growth_1y': 200,
        })
        assert r.status_code == 200
        body = r.get_json()
        assert body['success'] is True
        assert body['data']['forecast']['source'] == 'user'
        assert body['data']['forecast']['growth_6m_implied'] == 100.0

    def test_quick_endpoint_empty_code(self, client):
        """空 code 返回 400"""
        r = client.post('/api/valuation/quick', json={'code': ''})
        assert r.status_code == 400
        body = r.get_json()
        assert '请输入股票代码' in body['error']

    def test_quick_endpoint_has_forecast_field(self, client):
        """返回的 data 必须包含 forecast 字段"""
        r = client.post('/api/valuation/quick', json={'code': '999999'})
        body = r.get_json()
        assert 'forecast' in body['data']
        assert 'source' in body['data']['forecast']
        assert 'has_data' in body['data']['forecast']

    def test_detail_endpoint_has_forecast(self, client):
        """POST /api/valuation/detail 返回的 data 必须包含 forecast 字段"""
        r = client.post('/api/valuation/detail', json={'code': '999999'})
        assert r.status_code == 200
        body = r.get_json()
        assert body['success'] is True
        assert 'forecast' in body['data']
