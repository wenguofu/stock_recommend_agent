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


# ── 回归测试: 蓝思科技 300433 估值 bug ──────────────────────

class TestLansTechnologyRegression:
    """蓝思科技 (300433) 估值 PEG 为空的回归测试

    历史 bug: 2026-03-31 一季报 EPS=-0.0284 (单季亏损),
    auto_fill_from_db 错误地把它当成 TTM EPS, 导致 PE 算不出, PEG=0。

    修复: TTM 优先用最新年报 EPS (2025-12-31 EPS=0.79), 负数时回退到机构预期
    """

    def test_eps_ttm_prefers_annual_over_quarterly_loss(self, fresh_quant_valuation):
        """季报亏损时, 应优先用年报 EPS 作为 TTM"""
        from sqlalchemy import text
        from models import get_db
        db = next(get_db())
        try:
            row = db.execute(text("""
                SELECT report_date, eps, pe_ttm FROM stock_financials
                WHERE code = '300433'
                ORDER BY report_date DESC LIMIT 4
            """)).fetchall()
        finally:
            db.close()

        if not row:
            pytest.skip("数据库中无 300433 数据, 跳过回归测试")

        # Mock realtime (get_realtime_data 在函数内 import, 用 sys.modules 拦截)
        mock_data_fetchers = MagicMock()
        mock_data_fetchers.get_realtime_data.return_value = {'current_price': 45.61, 'name': '蓝思科技'}
        with patch.dict(sys.modules, {'data_fetchers': mock_data_fetchers}):
            result = fresh_quant_valuation.quick_valuation(
                code='300433', industry_growth_6m=34, industry_growth_1y=30,
            )

        eps_ttm = result.get('eps_ttm', 0)
        assert eps_ttm > 0, f"TTM EPS 仍为 {eps_ttm}, 修复失败"

        peg = result.get('peg_ratio', 0)
        assert peg > 0, f"PEG 比率仍为 {peg}, 估值无法计算"

        pe = result.get('current_pe', 0)
        assert pe > 0, f"current_pe 仍为 {pe}, 估值失败"

    def test_negative_quarter_eps_fallback_to_analyst(self, fresh_quant_valuation):
        """单元测试: TTM 为负时, 回退到机构预期 EPS_2026E"""
        from sqlalchemy.exc import OperationalError

        # Mock: SessionLocal 抛 OperationalError, 模拟 DB 不可用
        mock_session = MagicMock()
        mock_session.query.side_effect = OperationalError(
            "SELECT", {}, Exception("table missing")
        )
        mock_models = MagicMock()
        mock_models.SessionLocal.return_value = mock_session

        mock_data_fetchers = MagicMock()
        mock_data_fetchers.get_realtime_data.return_value = {'current_price': 10}

        mock_fc = {
            'net_profit_2025a': 5.0, 'net_profit_2026e': 10.0, 'net_profit_2027e': 15.0,
            'eps_2026e': 1.5, 'eps_2027e': 2.25,
            'analyst_count': 5, 'rating_label': '买入', 'updated_at': '',
            'has_data': True,
        }
        with patch.dict(sys.modules, {'models': mock_models, 'data_fetchers': mock_data_fetchers}):
            with patch.object(fresh_quant_valuation, 'get_institutional_forecast', return_value=mock_fc):
                inp = fresh_quant_valuation.ValuationInput(code='999999')
                inp = fresh_quant_valuation.auto_fill_from_db(inp)

                # TTM 数据库不可用 → 仍为 0 → 回退到机构预期 1.5
                assert inp.eps_ttm == 1.5, f"应为机构预期 1.5, 实际 {inp.eps_ttm}"
                assert inp.forecast_source == "institutional"


# ── Sprint 7: 成长股分类 ──────────────────────────────

class TestGrowthClass:
    """Sprint 7 优化: 成长股分类"""

    def test_sector_keyword_growth(self, fresh_quant_valuation):
        """行业关键词命中 → 成长股"""
        inp = fresh_quant_valuation.ValuationInput(
            code='300308', sector_name='光模块',
        )
        cls = fresh_quant_valuation.classify_growth_stock(inp)
        assert cls == "growth"
        assert inp.growth_class == "growth"
        assert "光模块" in inp.growth_class_reason

    def test_sector_keyword_cyclical(self, fresh_quant_valuation):
        """周期行业关键词 → 周期股"""
        inp = fresh_quant_valuation.ValuationInput(
            code='600188', sector_name='煤炭',
        )
        cls = fresh_quant_valuation.classify_growth_stock(inp)
        assert cls == "cyclical"
        assert inp.growth_class == "cyclical"

    def test_sector_keyword_pcb(self, fresh_quant_valuation):
        """PCB 是 AI/光模块上游, 归为成长股"""
        inp = fresh_quant_valuation.ValuationInput(
            code='300476', sector_name='PCB',
        )
        cls = fresh_quant_valuation.classify_growth_stock(inp)
        assert cls == "growth"

    def test_high_growth_high_roe(self, fresh_quant_valuation):
        """高增速 + 高 ROE → 成长股"""
        inp = fresh_quant_valuation.ValuationInput(
            code='999999', industry_growth_1y=80, roe=18,
        )
        cls = fresh_quant_valuation.classify_growth_stock(inp)
        assert cls == "growth"
        assert "ROE" in inp.growth_class_reason or "高增速" in inp.growth_class_reason

    def test_low_growth_value(self, fresh_quant_valuation):
        """低增速 → 价值股"""
        inp = fresh_quant_valuation.ValuationInput(
            code='999998', industry_growth_1y=3, roe=8,
        )
        cls = fresh_quant_valuation.classify_growth_stock(inp)
        assert cls == "value"

    def test_growth_class_params(self, fresh_quant_valuation):
        """不同分类的估值参数不同"""
        growth_params = fresh_quant_valuation.GROWTH_CLASS_PARAMS["growth"]
        value_params = fresh_quant_valuation.GROWTH_CLASS_PARAMS["value"]
        cyclical_params = fresh_quant_valuation.GROWTH_CLASS_PARAMS["cyclical"]
        # 成长股 base_pe 应该 > 价值股 > 周期股
        assert growth_params["base_pe"] > value_params["base_pe"] > cyclical_params["base_pe"]
        # 成长股 fair_pe 上限倍数最大
        assert growth_params["fair_pe_multiplier"] > value_params["fair_pe_multiplier"]


# ── Sprint 7: 新评分卡 ──────────────────────────────

class TestNewCompositeScore:
    """Sprint 7: DCF 为锚的新评分卡"""

    def test_dcf_margin_calculated(self, fresh_quant_valuation):
        """DCF margin 应正确计算: (DCF-price)/DCF * 100"""
        inp = fresh_quant_valuation.ValuationInput(
            code='300308', current_price=856, eps_ttm=10,
            industry_growth_1y=100,
        )
        result = fresh_quant_valuation.calculate_valuation(inp)
        # DCF 字段应存在且非 0 (因有 EPS)
        assert hasattr(result, 'dcf_margin')
        assert hasattr(result, 'dcf_value')
        # margin_of_safety 仍存在 (兼容)
        assert hasattr(result, 'margin_of_safety')

    def test_growth_class_affects_base_pe(self, fresh_quant_valuation):
        """成长股分类应该影响 base_pe"""
        # 同一只股票, 设为光模块 (growth) vs 默认 (value)
        inp_growth = fresh_quant_valuation.ValuationInput(
            code='300308', current_price=100, eps_ttm=1, sector_name='光模块',
        )
        inp_value = fresh_quant_valuation.ValuationInput(
            code='300308', current_price=100, eps_ttm=1, sector_name='其他',
        )
        r_growth = fresh_quant_valuation.calculate_valuation(inp_growth)
        r_value = fresh_quant_valuation.calculate_valuation(inp_value)
        # 成长股的 base_pe 应该 > 价值股
        assert r_growth.detail['base_pe'] > r_value.detail['base_pe']
        # 分类标签
        assert r_growth.detail['growth_class'] == 'growth'
        assert r_value.detail['growth_class'] == 'value'

    def test_momentum_adjustment_affects_score(self, fresh_quant_valuation):
        """动量调整应该影响评分"""
        inp = fresh_quant_valuation.ValuationInput(
            code='300308', current_price=100, eps_ttm=1,
        )
        r_neutral = fresh_quant_valuation.calculate_valuation(inp, momentum_adjustment=0)
        r_positive = fresh_quant_valuation.calculate_valuation(inp, momentum_adjustment=8)
        r_negative = fresh_quant_valuation.calculate_valuation(inp, momentum_adjustment=-8)
        # 正动量加分, 负动量减分
        assert r_positive.composite_score > r_neutral.composite_score
        assert r_negative.composite_score < r_neutral.composite_score
        # 但动量调整有截断 (±5)
        assert r_positive.composite_score - r_neutral.composite_score <= 5
        assert r_neutral.composite_score - r_negative.composite_score <= 5

    def test_institutional_rating_affects_score(self, fresh_quant_valuation):
        """机构评级应该影响评分"""
        inp_buy = fresh_quant_valuation.ValuationInput(
            code='300308', current_price=100, eps_ttm=1,
            forecast_rating_label='买入', forecast_analyst_count=20,
        )
        inp_sell = fresh_quant_valuation.ValuationInput(
            code='300308', current_price=100, eps_ttm=1,
            forecast_rating_label='卖出', forecast_analyst_count=5,
        )
        r_buy = fresh_quant_valuation.calculate_valuation(inp_buy)
        r_sell = fresh_quant_valuation.calculate_valuation(inp_sell)
        # 买入评级应该 > 卖出评级
        assert r_buy.composite_score > r_sell.composite_score
        # 差距应该 > 15 (评级差 12 + 覆盖家数差 3)
        assert r_buy.composite_score - r_sell.composite_score >= 15

    def test_dcf_centric_scoring(self, fresh_quant_valuation):
        """DCF 上行空间大的应该比 DCF 下行空间大的得分高"""
        # 情景 A: 股价低于 DCF (适度低估)
        inp_under = fresh_quant_valuation.ValuationInput(
            code='999999', current_price=80, eps_ttm=2,  # PE 40, 适度高估
            industry_growth_1y=30,
        )
        # 情景 B: 股价高于 DCF (明显高估)
        inp_over = fresh_quant_valuation.ValuationInput(
            code='999998', current_price=150, eps_ttm=2,  # PE 75, 严重高估
            industry_growth_1y=30,
        )
        r_under = fresh_quant_valuation.calculate_valuation(inp_under)
        r_over = fresh_quant_valuation.calculate_valuation(inp_over)
        # DCF 主导下, 低估应该比高估得分高
        assert r_under.composite_score > r_over.composite_score
        # 差距应该明显 (>10 分)
        assert r_under.composite_score - r_over.composite_score >= 10


# ── Sprint 7: 端到端集成测试 ──────────────────────────────

class TestSprint7EndToEnd:
    """Sprint 7 集成测试: 验证真实股票的回测表现"""

    def test_zhongji_xuchuang_5month_growth_recommend(self, fresh_quant_valuation):
        """中际旭创 5 月初: 评分应 >= 65 (推荐, 而非"持有")"""
        from sqlalchemy import text
        from models import get_db
        db = next(get_db())
        try:
            row = db.execute(text("SELECT report_date, eps, pe_ttm FROM stock_financials WHERE code='300308' ORDER BY report_date DESC LIMIT 1")).fetchone()
        finally:
            db.close()
        if not row:
            pytest.skip("数据库中无 300308 数据")

        # 用 DB 中的真实 EPS (annual), 5月初 ¥856 + 光模块行业
        db_eps = float(row[1]) if row[1] and float(row[1]) > 0 else 5.84
        inp = fresh_quant_valuation.ValuationInput(
            code='300308', current_price=856, eps_ttm=db_eps, sector_name='光模块',
            industry_growth_6m=175, industry_growth_1y=118,
            forecast_rating_label='买入', forecast_analyst_count=29,
        )
        result = fresh_quant_valuation.calculate_valuation(inp)
        # 关键断言: 5月初应该 ≥ 60 (持有偏积极/推荐, 而非旧的"持有"50)
        assert result.composite_score >= 60, f"5月初评分应 >= 60, 实际 {result.composite_score}, 旧版 50"
        # 分类应该是成长股
        assert result.detail['growth_class'] == 'growth'

    def test_yuanjie_5_18_crash_strong_recommend(self, fresh_quant_valuation):
        """源杰科技 5/18 暴跌后: 评分应 >= 75 (强烈推荐, 暴跌买入机会)"""
        from sqlalchemy import text
        from models import get_db
        db = next(get_db())
        try:
            row = db.execute(text("SELECT report_date, eps, pe_ttm FROM stock_financials WHERE code='688498' ORDER BY report_date DESC LIMIT 1")).fetchone()
        finally:
            db.close()
        if not row:
            pytest.skip("数据库中无 688498 数据")

        # 用 DB 中的真实 EPS, 5/18 暴跌后 ¥1058 + 光模块芯片行业
        db_eps = float(row[1]) if row[1] and float(row[1]) > 0 else 9.57
        inp = fresh_quant_valuation.ValuationInput(
            code='688498', current_price=1058, eps_ttm=db_eps, sector_name='光模块芯片',
            industry_growth_6m=327, industry_growth_1y=178,
            forecast_rating_label='买入', forecast_analyst_count=10,
        )
        result = fresh_quant_valuation.calculate_valuation(inp)
        # 关键断言: 暴跌后应该是"强烈推荐" (评分 >= 75)
        assert result.composite_score >= 75, f"5/18 暴跌后评分应 >= 75, 实际 {result.composite_score}"


class TestSprint7P1Momentum:
    """Sprint 7 P1.2: calculate_momentum_adjustment 单元测试"""

    def _make_kline(self, closes):
        """生成 K 线测试数据 (近 30 个交易日)"""
        return [{'day': f'2026-05-{15 - i:02d}', 'open': str(c), 'high': str(c),
                 'low': str(c), 'close': str(c), 'volume': '1000000'}
                for i, c in enumerate(closes)]

    def test_strong_uptrend_returns_positive(self, fresh_quant_valuation):
        """5d +15%, 20d +25% → 强上涨趋势 → 应返回正分"""
        closes = [100] * 20 + [105, 110, 115, 120, 125]  # 最后 5 天每天 +5%
        kline = self._make_kline(closes)
        adj = fresh_quant_valuation.calculate_momentum_adjustment('test', kline)
        assert adj > 0, f"强上涨应得正分, 实际 {adj}"

    def test_strong_downtrend_returns_negative(self, fresh_quant_valuation):
        """5d -15%, 20d -25% → 强下跌 → 应返回负分"""
        # 25 天, 早 20 天从 100 涨到 125, 然后 5 天跌回 100
        closes = [100, 105, 110, 115, 120, 125] + [125] * 14 + [120, 115, 110, 105, 100]
        kline = self._make_kline(closes)
        adj = fresh_quant_valuation.calculate_momentum_adjustment('test', kline)
        assert adj < 0, f"强下跌应得负分, 实际 {adj}"

    def test_sideways_returns_zero(self, fresh_quant_valuation):
        """横盘 → 应接近 0"""
        closes = [100] * 25
        kline = self._make_kline(closes)
        adj = fresh_quant_valuation.calculate_momentum_adjustment('test', kline)
        assert -1 <= adj <= 1, f"横盘应得 0 分, 实际 {adj}"

    def test_crash_then_rebound_bonus(self, fresh_quant_valuation):
        """暴跌反弹 (近 10 日单日 < -10%, 5 日累计 > +5%) → 应大 + 分"""
        # 30 天: 前 24 天平稳 100, 第 25 天暴跌到 80 (-20%), 然后 5 天反弹到 95 (+18.75%)
        closes = [100] * 24 + [80, 85, 88, 92, 95, 98]
        kline = self._make_kline(closes)
        adj = fresh_quant_valuation.calculate_momentum_adjustment('test', kline)
        assert adj >= 6, f"暴跌反弹应得大加分 (>=6), 实际 {adj}"

    def test_clamped_to_range(self, fresh_quant_valuation):
        """极值应被截断在 [-10, +10] 范围内"""
        closes = [100] + [200] * 25  # 5d +100%
        kline = self._make_kline(closes)
        adj = fresh_quant_valuation.calculate_momentum_adjustment('test', kline)
        assert -10 <= adj <= 10, f"动量分应截断在 [-10, 10], 实际 {adj}"

    def test_insufficient_data_returns_zero(self, fresh_quant_valuation):
        """数据不足 (< 5 天) → 应返回 0"""
        kline = self._make_kline([100, 101, 102])
        adj = fresh_quant_valuation.calculate_momentum_adjustment('test', kline)
        assert adj == 0.0


class TestSprint7P2RelativeStrength:
    """Sprint 7 P2: calculate_relative_strength_adjustment 单元测试"""

    def test_strong_outperformer(self, fresh_quant_valuation):
        """个股 5d +15%, 大盘 +0% → 跑赢 +15% → 强势加分"""
        # mock _fetch_kline_data: code 'XXX' → 个股强, 'sh000300' → 大盘平
        from unittest.mock import patch

        def fake_kline(code, days=30):
            if code == 'sh000300':
                closes = [4000] * 25  # 大盘平
            else:
                closes = [100] * 20 + [110, 115]  # 个股 +15%
            return [{'day': f'd{i}', 'open': str(c), 'high': str(c),
                     'low': str(c), 'close': str(c), 'volume': '0'} for i, c in enumerate(closes)]

        with patch.object(fresh_quant_valuation, '_fetch_kline_data', side_effect=fake_kline):
            adj = fresh_quant_valuation.calculate_relative_strength_adjustment('300308')
        assert adj >= 4, f"跑赢 +15% 应得 >= 4, 实际 {adj}"

    def test_weak_underperformer(self, fresh_quant_valuation):
        """个股 5d -10%, 大盘 +0% → 跑输 -10% → 弱势减分"""
        from unittest.mock import patch

        def fake_kline(code, days=30):
            if code == 'sh000300':
                closes = [4000] * 25
            else:
                closes = [100] * 20 + [95, 90]  # 个股 -10%
            return [{'day': f'd{i}', 'open': str(c), 'high': str(c),
                     'low': str(c), 'close': str(c), 'volume': '0'} for i, c in enumerate(closes)]

        with patch.object(fresh_quant_valuation, '_fetch_kline_data', side_effect=fake_kline):
            adj = fresh_quant_valuation.calculate_relative_strength_adjustment('300308')
        assert adj <= -1, f"跑输 -10% 应得 <= -1, 实际 {adj}"

    def test_neutral_market_match(self, fresh_quant_valuation):
        """个股和大盘涨幅一致 → 应接近 0"""
        from unittest.mock import patch

        def fake_kline(code, days=30):
            closes = [100] * 20 + [105, 110]  # 都涨 10%
            return [{'day': f'd{i}', 'open': str(c), 'high': str(c),
                     'low': str(c), 'close': str(c), 'volume': '0'} for i, c in enumerate(closes)]

        with patch.object(fresh_quant_valuation, '_fetch_kline_data', side_effect=fake_kline):
            adj = fresh_quant_valuation.calculate_relative_strength_adjustment('300308')
        assert -1 <= adj <= 1, f"同步涨跌应得 0, 实际 {adj}"

    def test_market_data_unavailable_returns_zero(self, fresh_quant_valuation):
        """大盘数据拉不到 → 应返回 0 (不阻塞主流程)"""
        from unittest.mock import patch

        def fake_kline(code, days=30):
            if code in ('sh000300', 'sz399300'):
                return []  # 大盘拉不到
            return [{'day': 'd', 'open': '1', 'high': '1', 'low': '1', 'close': '1', 'volume': '0'}] * 25

        with patch.object(fresh_quant_valuation, '_fetch_kline_data', side_effect=fake_kline):
            adj = fresh_quant_valuation.calculate_relative_strength_adjustment('300308')
        assert adj == 0.0

    def test_clamped_to_range(self, fresh_quant_valuation):
        """RS 调整分应截断在 [-5, +5]"""
        from unittest.mock import patch

        def fake_kline(code, days=30):
            if code == 'sh000300':
                closes = [1000] * 25  # 大盘平
            else:
                closes = [100] + [200] * 24  # 个股翻倍
            return [{'day': f'd{i}', 'open': str(c), 'high': str(c),
                     'low': str(c), 'close': str(c), 'volume': '0'} for i, c in enumerate(closes)]

        with patch.object(fresh_quant_valuation, '_fetch_kline_data', side_effect=fake_kline):
            adj = fresh_quant_valuation.calculate_relative_strength_adjustment('300308')
        assert -5 <= adj <= 5, f"RS 应截断在 [-5, 5], 实际 {adj}"


class TestSprint7P1P2Integration:
    """Sprint 7 P1+P2 集成: 验证 calculate_valuation 接收 momentum_adjustment 后的打分变化"""

    def test_positive_momentum_lifts_score(self, fresh_quant_valuation):
        """正向动量调整 → 评分应增加"""
        base_inp = fresh_quant_valuation.ValuationInput(
            code='300308', current_price=1000, eps_ttm=15, pe_ttm=66, roe=25,
            revenue_yoy=80, profit_yoy=120, sector_name='光模块',
            industry_growth_6m=100, industry_growth_1y=80,
        )
        base = fresh_quant_valuation.calculate_valuation(base_inp, momentum_adjustment=0)
        boosted = fresh_quant_valuation.calculate_valuation(base_inp, momentum_adjustment=8)
        assert boosted.composite_score > base.composite_score, \
            f"动量 +8 应提分: 基准={base.composite_score} 提升后={boosted.composite_score}"

    def test_negative_momentum_caps_score_drop(self, fresh_quant_valuation):
        """负向动量调整 → 评分应下降 (但被截断在 -5)"""
        base_inp = fresh_quant_valuation.ValuationInput(
            code='300308', current_price=1000, eps_ttm=15, pe_ttm=66, roe=25,
            revenue_yoy=80, profit_yoy=120, sector_name='光模块',
            industry_growth_6m=100, industry_growth_1y=80,
        )
        base = fresh_quant_valuation.calculate_valuation(base_inp, momentum_adjustment=0)
        negative = fresh_quant_valuation.calculate_valuation(base_inp, momentum_adjustment=-5)
        assert negative.composite_score < base.composite_score, \
            f"动量 -5 应降分: 基准={base.composite_score} 降低后={negative.composite_score}"
        # 截断验证: 给 -20 也只能减 5 分
        extreme = fresh_quant_valuation.calculate_valuation(base_inp, momentum_adjustment=-20)
        assert extreme.composite_score == negative.composite_score, \
            f"动量截断应限制在 -5: -20 实际效果={extreme.composite_score}, 期望={negative.composite_score}"

