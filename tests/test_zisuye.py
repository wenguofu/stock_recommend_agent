"""
tests/test_zisuye.py
紫苏叶选股策略 — 单元测试

覆盖:
  1) 评分子项: _score_industry / _score_elasticity / _score_mispricing
  2) 市值估算: _estimate_market_cap_yi
  3) 主流程 screen_zisuye: 用 MySQL 测试 schema + 临时数据
  4) 入库/读取: save_shiso_picks / list_shiso_picks
  5) 风控: 市值/成交额过滤
"""
import os
import sys
import json
import pytest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import sessionmaker

import models  # noqa
from models import (
    Base, ShisoChain, ShisoChokepoint, ShisoPick,
    StockFinancial, BacktestData, BacktestStockMeta,
)
from db import (
    upsert_shiso_chain, upsert_shiso_chokepoint,
    save_shiso_picks, list_shiso_picks,
)

import strategies.zisuye as zisuye


# ═══════════════════════════════════════════════════════════════
# Fixture: MySQL 测试 schema + 替换全局 SessionLocal
# ═══════════════════════════════════════════════════════════════

@pytest.fixture(scope="function")
def test_db(mysql_test_schema, monkeypatch):
    """MySQL 临时 schema + 替换 models.engine/SessionLocal, teardown 还原"""
    orig_engine = models.engine
    orig_session = models.SessionLocal
    orig_zisuye_session = zisuye.SessionLocal
    TestSession = sessionmaker(bind=mysql_test_schema)
    monkeypatch.setattr(models, "engine", mysql_test_schema)
    monkeypatch.setattr(models, "SessionLocal", TestSession)
    monkeypatch.setattr(zisuye, "SessionLocal", TestSession)
    try:
        yield TestSession
    finally:
        models.engine = orig_engine
        models.SessionLocal = orig_session
        zisuye.SessionLocal = orig_zisuye_session


def _insert_financial(session, code, **kw):
    """灌一条财务数据"""
    row = StockFinancial(
        code=code,
        report_date=kw.get("report_date", "2025-12-31"),
        report_type=kw.get("report_type", "年报"),
        revenue=kw.get("revenue"),
        net_profit=kw.get("net_profit"),
        roe=kw.get("roe"),
        gross_margin=kw.get("gross_margin"),
        pe_ttm=kw.get("pe_ttm"),
        pb=kw.get("pb"),
        pe_industry=kw.get("pe_industry"),
        pb_industry=kw.get("pb_industry"),
        revenue_yoy=kw.get("revenue_yoy"),
        profit_yoy=kw.get("profit_yoy"),
    )
    session.add(row)
    session.commit()


def _insert_backtest(session, code, date, close, turnover, amount,
                     change_pct=0.0, volume=0.0):
    row = BacktestData(
        code=code, date=date,
        open=close, close=close, high=close, low=close,
        volume=volume, amount=amount,
        change_pct=change_pct, turnover=turnover,
    )
    session.add(row)
    session.commit()


def _insert_meta(session, code, name, sector=""):
    row = BacktestStockMeta(
        code=code, name=name, sector=sector,
        data_start="2024-01-01", data_end="2025-12-31", total_days=240,
    )
    session.add(row)
    session.commit()


def _seed_chain(session, chain_name="AI光通信", enabled=True):
    upsert_shiso_chain(
        session, chain_name=chain_name,
        sector_tag="通信",
        toro_layer="GPU/光模块",
        chokepoint_layer="InP衬底",
        top_down_path="AI→GPU→光模块→InP",
        enabled=enabled, notes="测试",
    )


# ═══════════════════════════════════════════════════════════════
# 1) 评分子项
# ═══════════════════════════════════════════════════════════════

class TestScoreIndustry:
    def test_monopoly_bonus_single_player(self):
        s = zisuye._score_industry(80, player_count=1)
        assert s == 85  # 80 + 5

    def test_three_player_penalty(self):
        s = zisuye._score_industry(80, player_count=3)
        assert s == 70  # 80 - 10

    def test_five_plus_player_big_penalty(self):
        s = zisuye._score_industry(80, player_count=6)
        assert s == 60  # 80 - 20

    def test_clamped_0_to_100(self):
        assert zisuye._score_industry(0, 5) == 0
        assert zisuye._score_industry(120, 1) == 100  # 120+5=125 → 100

    def test_none_handling(self):
        s = zisuye._score_industry(None, 3)
        # None → 50, -10 = 40
        assert s == 40

    def test_duopoly_sweet_spot(self):
        """player_count=2 是双寡头 sweet spot, 应给 +2 小加分"""
        s = zisuye._score_industry(80, player_count=2)
        assert s == 82  # 80 + 2

    def test_weight_validation(self):
        """weights 缺键应抛 ValueError 而不是 KeyError"""
        with pytest.raises(ValueError, match="缺少键"):
            zisuye._validate_weights({"industry": 0.5})  # 缺 elasticity/mispricing
        with pytest.raises(ValueError, match="缺少键"):
            zisuye._validate_weights({})
        # 完整 keys 不报错
        zisuye._validate_weights({"industry": 0.4, "elasticity": 0.3, "mispricing": 0.3})


class TestScoreElasticity:
    def test_strong_growth(self):
        fin = {"revenue_yoy": 60, "profit_yoy": 80, "roe": 18, "gross_margin": 45}
        s = zisuye._score_elasticity(fin)
        # 30 + 30 + 20 + 20 = 100
        assert s == 100

    def test_weak_growth(self):
        fin = {"revenue_yoy": 5, "profit_yoy": 3, "roe": 6, "gross_margin": 18}
        s = zisuye._score_elasticity(fin)
        # 10 + 15 + 8 + 8 = 41
        assert s == 41

    def test_negative_growth_zero_score(self):
        fin = {"revenue_yoy": -10, "profit_yoy": -20}
        s = zisuye._score_elasticity(fin)
        assert s == 0

    def test_missing_fields(self):
        s = zisuye._score_elasticity({})
        assert s == 0


class TestScoreMispricing:
    def test_extreme_discount(self):
        fin = {"pe_ttm": 5, "pe_industry": 100, "pb": 1, "pb_industry": 5}
        s = zisuye._score_mispricing(fin, turnover=0.5)
        # PE 30 + PB 25 + 冷门 45 = 100
        assert s == 100

    def test_hot_popular(self):
        fin = {"pe_ttm": 100, "pe_industry": 50, "pb": 10, "pb_industry": 5}
        s = zisuye._score_mispricing(fin, turnover=15.0)
        # PE 5 + PB 5 + hot 5 = 15
        assert s == 15

    def test_only_turnover(self):
        s = zisuye._score_mispricing({}, turnover=0.5)
        assert s == 45  # 只有冷门分


class TestEstimateMarketCap:
    def test_basic(self):
        # amount=1e8 (1亿), turnover=5%
        # shares = 1e8/price/0.05, mkt_cap = price * shares = 1e8/0.05 = 2e9
        # 转亿 = 20亿
        mc = zisuye._estimate_market_cap_yi(price=10, amount=1e8, turnover=5)
        assert mc == pytest.approx(20.0)

    def test_zero_inputs(self):
        assert zisuye._estimate_market_cap_yi(0, 1e8, 5) is None
        assert zisuye._estimate_market_cap_yi(10, 0, 5) is None
        assert zisuye._estimate_market_cap_yi(10, 1e8, 0) is None

    def test_zero_turnover(self):
        assert zisuye._estimate_market_cap_yi(10, 1e8, 0) is None


# ═══════════════════════════════════════════════════════════════
# 2) 主流程
# ═══════════════════════════════════════════════════════════════

class TestScreenZisuye:
    def test_empty_chokepoints_returns_empty(self, test_db):
        result = zisuye.screen_zisuye()
        assert result["strategy"] == "zisuye"
        assert result["count"] == 0

    def test_basic_pipeline(self, test_db):
        session = test_db()
        try:
            # 灌产业链 + 2 个卡位 (1个强、1个弱)
            _seed_chain(session, "AI光通信")
            upsert_shiso_chokepoint(
                session, code="688498", chain_name="AI光通信",
                name="源杰科技", layer="DFB激光器",
                monopoly_score=85, player_count=2,
                moat_note="国内DFB主力", extra_score=15,
            )
            upsert_shiso_chokepoint(
                session, code="300548", chain_name="AI光通信",
                name="博创科技", layer="光模块",
                monopoly_score=40, player_count=6,
                moat_note="中游模块", extra_score=-10,
            )

            # 灌行情
            _insert_meta(session, "688498", "源杰科技")
            _insert_meta(session, "300548", "博创科技")
            _insert_backtest(session, "688498", "2025-12-30",
                             close=120.0, turnover=2.5, amount=1.5e8)
            _insert_backtest(session, "300548", "2025-12-30",
                             close=30.0, turnover=8.0, amount=2e8)

            # 灌财务
            _insert_financial(session, "688498",
                              roe=18, gross_margin=45,
                              revenue_yoy=60, profit_yoy=80,
                              pe_ttm=40, pb=5,
                              pe_industry=80, pb_industry=8)
            _insert_financial(session, "300548",
                              roe=8, gross_margin=20,
                              revenue_yoy=10, profit_yoy=5,
                              pe_ttm=50, pb=4,
                              pe_industry=60, pb_industry=5)
        finally:
            session.close()

        result = zisuye.screen_zisuye()

        assert result["count"] == 2
        # 源杰(强) 应该排第一
        assert result["stocks"][0]["code"] == "688498"
        assert result["stocks"][1]["code"] == "300548"

        # 第一名总分应该明显高于第二名
        s1 = result["stocks"][0]["total_score"]
        s2 = result["stocks"][1]["total_score"]
        assert s1 > s2 + 20  # 至少差 20 分

        # 三项分字段都应填了
        for k in ("industry_score", "elasticity_score", "mispricing_score", "extra_score"):
            assert k in result["stocks"][0]

    def test_amount_filter_rejects_illiquid(self, test_db):
        session = test_db()
        try:
            _seed_chain(session)
            upsert_shiso_chokepoint(
                session, code="688498", chain_name="AI光通信",
                name="源杰科技", layer="DFB", monopoly_score=85, player_count=2,
            )
            _insert_backtest(session, "688498", "2025-12-30",
                             close=120.0, turnover=2.0, amount=2000)  # 2000元 < 5000万
        finally:
            session.close()

        result = zisuye.screen_zisuye()
        assert result["count"] == 0  # 被流动性过滤掉

    def test_market_cap_filter(self, test_db):
        """市值 >200亿 应该被过滤"""
        session = test_db()
        try:
            _seed_chain(session)
            upsert_shiso_chokepoint(
                session, code="688498", chain_name="AI光通信",
                name="源杰科技", layer="DFB", monopoly_score=85, player_count=2,
            )
            _insert_backtest(session, "688498", "2025-12-30",
                             close=100.0, turnover=0.5, amount=5e8)
            # amount=5亿, turnover=0.5% → mkt_cap ≈ 5e8*100/0.5/1e8 = 1000亿
        finally:
            session.close()

        result = zisuye.screen_zisuye()
        assert result["count"] == 0  # 1000亿 > 200亿, 被过滤

    def test_low_price_filter(self, test_db):
        session = test_db()
        try:
            _seed_chain(session)
            upsert_shiso_chokepoint(
                session, code="688498", chain_name="AI光通信",
                name="源杰科技", layer="DFB", monopoly_score=85, player_count=2,
            )
            _insert_backtest(session, "688498", "2025-12-30",
                             close=1.5, turnover=2.0, amount=1e8)
        finally:
            session.close()

        result = zisuye.screen_zisuye()
        assert result["count"] == 0  # 价格 <2, 垃圾股过滤

    def test_chain_filter(self, test_db):
        session = test_db()
        try:
            _seed_chain(session, "AI光通信")
            _seed_chain(session, "半导体材料")
            upsert_shiso_chokepoint(
                session, code="688498", chain_name="AI光通信",
                name="源杰科技", layer="DFB", monopoly_score=85, player_count=2,
            )
            upsert_shiso_chokepoint(
                session, code="688126", chain_name="半导体材料",
                name="沪硅产业", layer="硅片", monopoly_score=70, player_count=3,
            )
            _insert_backtest(session, "688498", "2025-12-30",
                             close=120, turnover=2, amount=1e8)
            _insert_backtest(session, "688126", "2025-12-30",
                             close=20, turnover=2, amount=1e8)
        finally:
            session.close()

        r1 = zisuye.screen_zisuye(chain_name="AI光通信")
        assert r1["count"] == 1
        assert r1["stocks"][0]["code"] == "688498"

        r2 = zisuye.screen_zisuye(chain_name="半导体材料")
        assert r2["count"] == 1
        assert r2["stocks"][0]["code"] == "688126"


# ═══════════════════════════════════════════════════════════════
# 3) 入库/读取
# ═══════════════════════════════════════════════════════════════

class TestPersistence:
    def test_save_and_list_picks(self, test_db):
        session = test_db()
        try:
            picks = [
                {"rank": 1, "code": "688498", "name": "源杰科技",
                 "price": 120, "total_score": 88, "chain_name": "AI光通信",
                 "industry_score": 90, "elasticity_score": 100, "mispricing_score": 80,
                 "extra_score": 15},
                {"rank": 2, "code": "688313", "name": "仕佳光子",
                 "price": 30, "total_score": 70, "chain_name": "AI光通信",
                 "industry_score": 70, "elasticity_score": 80, "mispricing_score": 60,
                 "extra_score": 8},
            ]
            ids = save_shiso_picks(session, pick_date="2025-12-30", picks=picks)
            assert len(ids) == 2

            rows = list_shiso_picks(session, pick_date="2025-12-30")
            assert len(rows) == 2
            assert rows[0].rank == 1
            assert rows[0].code == "688498"
            assert rows[0].total_score == 88
        finally:
            session.close()

    def test_save_overwrites_same_date(self, test_db):
        session = test_db()
        try:
            picks_v1 = [{"rank": 1, "code": "X", "name": "X", "total_score": 50}]
            picks_v2 = [{"rank": 1, "code": "Y", "name": "Y", "total_score": 80}]
            save_shiso_picks(session, pick_date="2025-12-30", picks=picks_v1)
            save_shiso_picks(session, pick_date="2025-12-30", picks=picks_v2)
            rows = list_shiso_picks(session, pick_date="2025-12-30")
            assert len(rows) == 1
            assert rows[0].code == "Y"
        finally:
            session.close()


# ═══════════════════════════════════════════════════════════════
# 4) run_and_save 端到端
# ═══════════════════════════════════════════════════════════════

class TestRunAndSave:
    def test_end_to_end(self, test_db):
        session = test_db()
        try:
            _seed_chain(session)
            upsert_shiso_chokepoint(
                session, code="688498", chain_name="AI光通信",
                name="源杰科技", layer="DFB", monopoly_score=85, player_count=2,
            )
            _insert_meta(session, "688498", "源杰科技")
            _insert_backtest(session, "688498", "2025-12-30",
                             close=120, turnover=2, amount=1e8)
            _insert_financial(session, "688498",
                              roe=18, gross_margin=45,
                              revenue_yoy=60, profit_yoy=80,
                              pe_ttm=40, pe_industry=80)
        finally:
            session.close()

        result = zisuye.run_and_save(pick_date="2025-12-30")
        assert result["count"] == 1

        # 检查入库
        session = test_db()
        try:
            rows = list_shiso_picks(session, pick_date="2025-12-30")
            assert len(rows) == 1
            assert rows[0].stop_loss_pct == -5.0  # 默认止损
            assert rows[0].trim_pct == 50.0
            assert abs(rows[0].trim_size - 1.0/3) < 1e-6
        finally:
            session.close()

    def test_amount_field_populated_in_pick(self, test_db):
        """验证 HIGH#2 修复: amount 字段在 pick 中被正确写入, 不再是 NULL"""
        session = test_db()
        try:
            _seed_chain(session)
            upsert_shiso_chokepoint(
                session, code="688498", chain_name="AI光通信",
                name="源杰科技", layer="DFB", monopoly_score=85, player_count=2,
            )
            _insert_backtest(session, "688498", "2025-12-30",
                             close=120, turnover=2, amount=2e8)  # 2 亿
        finally:
            session.close()

        result = zisuye.run_and_save(pick_date="2025-12-30")
        assert result["count"] == 1
        # 验证 result 里有 amount
        pick = result["stocks"][0]
        assert "amount" in pick
        assert pick["amount"] == pytest.approx(2e8, rel=0.01)

        # 验证 DB row 的 amount 字段也是非 NULL
        session = test_db()
        try:
            rows = list_shiso_picks(session, pick_date="2025-12-30")
            assert rows[0].amount is not None
            assert rows[0].amount == pytest.approx(2e8, rel=0.01)
        finally:
            session.close()

    def test_report_date_field_populated_in_pick(self, test_db):
        """验证 HIGH#1 修复: report_date 不再是 NULL"""
        session = test_db()
        try:
            _seed_chain(session)
            upsert_shiso_chokepoint(
                session, code="688498", chain_name="AI光通信",
                name="源杰科技", layer="DFB", monopoly_score=85, player_count=2,
            )
            _insert_backtest(session, "688498", "2025-12-30",
                             close=120, turnover=2, amount=1e8)
            _insert_financial(session, "688498",
                              report_date="2025-09-30",
                              roe=18, gross_margin=45,
                              revenue_yoy=60, profit_yoy=80)
        finally:
            session.close()

        result = zisuye.run_and_save(pick_date="2025-12-30")
        assert result["count"] == 1
        pick = result["stocks"][0]
        assert pick["report_date"] == "2025-09-30"  # 不再是 None


class TestEnabledFilter:
    """MEDIUM#5: 验证 enabled=False 的卡位被过滤"""

    def test_disabled_chokepoint_excluded(self, test_db):
        session = test_db()
        try:
            _seed_chain(session)
            # 一个 enabled, 一个 disabled
            upsert_shiso_chokepoint(
                session, code="688498", chain_name="AI光通信",
                name="源杰科技", layer="DFB", monopoly_score=85, player_count=2,
                enabled=True,
            )
            upsert_shiso_chokepoint(
                session, code="688313", chain_name="AI光通信",
                name="仕佳光子", layer="AWG", monopoly_score=80, player_count=2,
                enabled=False,  # 显式禁用
            )
            _insert_backtest(session, "688498", "2025-12-30",
                             close=120, turnover=2, amount=1e8)
            _insert_backtest(session, "688313", "2025-12-30",
                             close=30, turnover=2, amount=1e8)
        finally:
            session.close()

        result = zisuye.screen_zisuye()
        assert result["count"] == 1  # 只有源杰科技被选中
        assert result["stocks"][0]["code"] == "688498"

    def test_disabled_chain_excluded(self, test_db):
        """整个 chain 被禁用时, 该链所有卡位都不参与"""
        session = test_db()
        try:
            # 创建一条 enabled=False 的链
            upsert_shiso_chain(
                session, chain_name="旧链",
                enabled=False,
                chokepoint_layer="test",
                top_down_path="test",
            )
            upsert_shiso_chokepoint(
                session, code="688498", chain_name="旧链",
                name="源杰科技", layer="DFB", monopoly_score=85, player_count=2,
                enabled=True,
            )
            _insert_backtest(session, "688498", "2025-12-30",
                             close=120, turnover=2, amount=1e8)
        finally:
            session.close()

        result = zisuye.screen_zisuye()
        assert result["count"] == 0  # 旧链被禁用, 0 候选


class TestDuplicateChainHandling:
    """MEDIUM#1 修复: 同一 code 多链时, 取 monopoly_score 最高的"""

    def test_picks_highest_monopoly_when_in_multiple_chains(self, test_db):
        session = test_db()
        try:
            # 必须先 seed 两条链, 否则 inner join 会过滤掉缺链的卡位
            _seed_chain(session, "AI光通信")
            _seed_chain(session, "半导体材料")
            # 同一 code 在两个 chain 中, monopoly_score 不同
            upsert_shiso_chokepoint(
                session, code="688498", chain_name="AI光通信",
                name="源杰科技", layer="DFB", monopoly_score=85, player_count=2,
            )
            upsert_shiso_chokepoint(
                session, code="688498", chain_name="半导体材料",  # 重复 code 不同链
                name="源杰科技", layer="其他", monopoly_score=50, player_count=5,
            )
            _insert_backtest(session, "688498", "2025-12-30",
                             close=120, turnover=2, amount=1e8)
        finally:
            session.close()

        result = zisuye.screen_zisuye()
        assert result["count"] == 1  # 同一 code 只出一条
        assert result["stocks"][0]["chain_name"] == "AI光通信"  # 取高分链
        assert result["chains_count"] == 1


class TestStrategyEngineIntegration:
    """HIGH#3 修复: 验证 strategy_engine 已注册 zisuye"""

    def test_zisuye_in_strategies_dict(self):
        """strategy_engine.STRATEGIES 必须含 'zisuye' 键"""
        import strategy_engine
        assert "zisuye" in strategy_engine.STRATEGIES
        cfg = strategy_engine.STRATEGIES["zisuye"]
        assert cfg["name"] == "紫苏叶"
        assert cfg["min_score"] > 0
        assert "desc" in cfg and len(cfg["desc"]) > 0

    def test_screen_stocks_dispatches_zisuye(self, monkeypatch, test_db):
        """screen_stocks('zisuye') 应正确分派到 strategies.zisuye.screen_zisuye"""
        import strategy_engine

        # 灌测试数据
        session = test_db()
        try:
            _seed_chain(session)
            upsert_shiso_chokepoint(
                session, code="688498", chain_name="AI光通信",
                name="源杰科技", layer="DFB", monopoly_score=85, player_count=2,
            )
            _insert_backtest(session, "688498", "2025-12-30",
                             close=120, turnover=2, amount=1e8)
        finally:
            session.close()

        # 通过 strategy_engine.screen_stocks('zisuye') 走
        picks = strategy_engine.screen_stocks("zisuye", top_n=5)
        assert len(picks) >= 1
        assert picks[0]["code"] == "688498"
        assert picks[0]["strategy"] == "zisuye"
        # zisuye 的 picks 应该带 chain_name / layer
        assert picks[0].get("chain_name") == "AI光通信"