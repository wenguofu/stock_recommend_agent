"""
测试 midline 中线真实预判:
  1. mid_term DL 可用时, 返回 DL 预测 (direction/prob_up/expected_return)
  2. mid_term DL 不可用时, 回落到 rule-based (基于 _score_stock 结果)
  3. 输出结构稳定 (即使 DL 失败, 字段都在, 不再静默 None)

后端实现位于 midline_routes.py:
  - 内部函数 _try_mid_term_dl(code) -> dict | None
  - 内部函数 _rule_based_midline_predict(score_dict) -> dict
  - 公开函数 midline_predict(code, dl_enabled=True) -> dict
"""
import os
import sys
from unittest import mock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestRuleBasedMidlinePredict:
    """规则 fallback 单元测试 — 不依赖 DL / torch。"""

    def test_high_health_with_bullish_macd_is_bullish(self):
        """总分 >= 70 + MACD 多头 → 看涨, prob_up >= 0.6。"""
        from midline_routes import _rule_based_midline_predict
        score = {"total": 85, "macd_signal": "多头"}
        result = _rule_based_midline_predict(score)
        assert result["mid_direction"] == "up"
        assert result["mid_prob_up"] >= 0.6
        assert result["mid_expected_return"] > 0

    def test_low_health_is_bearish(self):
        """总分 <= 30 → 看跌, prob_down >= 0.55。"""
        from midline_routes import _rule_based_midline_predict
        score = {"total": 20, "macd_signal": "金叉初期"}
        result = _rule_based_midline_predict(score)
        assert result["mid_direction"] == "down"
        assert result["mid_prob_down"] >= 0.55
        assert result["mid_expected_return"] < 0

    def test_death_cross_is_bearish_even_with_mid_health(self):
        """MACD 死叉 (即使总分 50) → 看跌。"""
        from midline_routes import _rule_based_midline_predict
        score = {"total": 50, "macd_signal": "死叉"}
        result = _rule_based_midline_predict(score)
        assert result["mid_direction"] == "down"

    def test_neutral_health_is_flat(self):
        """总分 40-60 且无明确信号 → 震荡, prob_up ~ 0.5。"""
        from midline_routes import _rule_based_midline_predict
        score = {"total": 50, "macd_signal": "金叉初期"}
        result = _rule_based_midline_predict(score)
        assert result["mid_direction"] == "flat"
        assert abs(result["mid_prob_up"] - 0.5) < 0.05

    def test_probs_sum_to_one(self):
        """三档概率加起来 = 1。"""
        from midline_routes import _rule_based_midline_predict
        for score in [
            {"total": 90, "macd_signal": "多头"},
            {"total": 10, "macd_signal": "死叉"},
            {"total": 50, "macd_signal": "金叉初期"},
        ]:
            r = _rule_based_midline_predict(score)
            s = r["mid_prob_up"] + r["mid_prob_down"] + r["mid_prob_flat"]
            assert abs(s - 1.0) < 0.01, f"概率和不等于 1: {s}"


class TestMidlinePredictDlPath:
    """DL 路径: mock _try_mid_term_dl, 验证 midline_predict 走 DL 路径。"""

    def test_dl_success_uses_mid_term_dl_model(self):
        """_try_mid_term_dl 返回 dict 时, midline_predict 标记 mid_model=mid_term_dl。"""
        fake_dl = {
            "mid_direction": "up",
            "mid_prob_up": 0.72,
            "mid_prob_down": 0.18,
            "mid_prob_flat": 0.10,
            "mid_expected_return": 0.045,
            "mid_horizon": "4w",
        }
        with mock.patch("midline_routes._try_mid_term_dl", return_value=fake_dl):
            from midline_routes import midline_predict
            result = midline_predict("000001", dl_enabled=True)
        assert result["mid_model"] == "mid_term_dl"
        assert result["mid_direction"] == "up"
        assert result["mid_prob_up"] == 0.72
        assert result["mid_horizon"] == "4w"
        assert result["mid_expected_return"] == 0.045

    def test_dl_disabled_uses_rule_based(self):
        """dl_enabled=False → 跳过 DL, 直接 rule-based。"""
        with mock.patch("midline_routes._try_mid_term_dl") as mock_dl, \
             mock.patch("midline_routes._score_stock", return_value={
                 "total": 85, "macd_signal": "多头", "ma_score": 35,
                 "rsi_score": 25, "trend": "强势多头", "suggestion": "持有",
             }):
            from midline_routes import midline_predict
            result = midline_predict("000001", dl_enabled=False)
        mock_dl.assert_not_called()
        assert result["mid_model"] == "rule_based"
        assert result["mid_direction"] == "up"


class TestMidlinePredictFallback:
    """DL 不可用 (返回 None) 时, 自动回落到 rule-based, 不再静默 None。"""

    def test_dl_returns_none_falls_back_to_rule_based(self):
        """_try_mid_term_dl 返回 None (checkpoint 缺失/feature 不足) → rule-based。"""
        with mock.patch("midline_routes._try_mid_term_dl", return_value=None), \
             mock.patch("midline_routes._score_stock", return_value={
                 "total": 50, "macd_signal": "金叉初期", "ma_score": 20,
                 "rsi_score": 15, "trend": "震荡", "suggestion": "观望",
             }):
            from midline_routes import midline_predict
            result = midline_predict("000001", dl_enabled=True)
        assert result["mid_model"] == "rule_based"
        assert result["mid_direction"] == "flat"
        # 必须有完整字段 (不静默 None)
        for k in ("mid_direction", "mid_prob_up", "mid_prob_down",
                  "mid_prob_flat", "mid_expected_return", "mid_horizon", "mid_model"):
            assert k in result
            assert result[k] is not None

    def test_dl_raises_exception_also_falls_back(self):
        """_try_mid_term_dl 抛异常 → rule-based (不崩溃)。"""
        with mock.patch("midline_routes._try_mid_term_dl",
                        side_effect=RuntimeError("checkpoint corrupted")), \
             mock.patch("midline_routes._score_stock", return_value={
                 "total": 85, "macd_signal": "多头", "ma_score": 35,
                 "rsi_score": 25, "trend": "强势多头", "suggestion": "持有",
             }):
            from midline_routes import midline_predict
            result = midline_predict("000001", dl_enabled=True)
        assert result["mid_model"] == "rule_based"
        assert result["mid_direction"] == "up"

    def test_rule_based_also_failing_returns_safe_default(self):
        """DL + rule_based 都失败 (e.g. data 不足) → 返回安全默认值 (flat, 0.5)。"""
        with mock.patch("midline_routes._try_mid_term_dl", return_value=None), \
             mock.patch("midline_routes._score_stock",
                        side_effect=Exception("no data")):
            from midline_routes import midline_predict
            result = midline_predict("000001", dl_enabled=True)
        # 不崩溃, 有合理默认值
        assert result["mid_direction"] == "flat"
        assert result["mid_prob_up"] == 0.5
        assert result["mid_model"] == "rule_based"
