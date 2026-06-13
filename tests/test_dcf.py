"""TDD Red — DCF 估值公式测试

覆盖 design.md dcf_valuation() 契约:
  - 5 年显式预测 (NPV_t = EPS_t × (1+g)^t / (1+r)^t)
  - Gordon 永续价值 (TV = EPS_5 × (1+g_t) / (r - g_t), 折现到 t=0)
  - 入参 (canonical short naming): growth / discount / terminal
  - 返回: {fair_value_per_share, current_price, upside_pct, assumptions, error?}
"""
import pytest


def test_dcf_normal_case_returns_expected_value():
    """EPS=1.0, 当前价=10, g=0.15, r=0.10, g_t=0.03 → 手算 fair value, 验证公式"""
    from services.dcf import dcf_valuation

    result = dcf_valuation(
        eps=1.0, current_price=10.0,
        growth=0.15, discount=0.10, terminal=0.03,
    )
    # 不应返回 error
    assert "error" not in result
    # 手算: 5 年显式
    expected_cf = 0
    for t in range(1, 6):
        cf_t = 1.0 * (1.15 ** t) / (1.10 ** t)
        expected_cf += cf_t
    # 永续价值
    tv = 1.0 * (1.15 ** 5) * (1.03) / (0.10 - 0.03)
    tv_pv = tv / (1.10 ** 5)
    expected_fair = expected_cf + tv_pv  # ~ 24.4
    assert abs(result["fair_value_per_share"] - round(expected_fair, 2)) < 0.05
    # 上行空间应为正 (fair > current)
    assert result["upside_pct"] > 0
    # 字段完整性
    assert result["current_price"] == 10.0
    assert result["assumptions"]["growth"] == 0.15
    assert result["assumptions"]["discount"] == 0.10
    assert result["assumptions"]["terminal"] == 0.03


def test_dcf_eps_zero_returns_error():
    """EPS = 0 → 错误路径, 不计算"""
    from services.dcf import dcf_valuation

    result = dcf_valuation(
        eps=0.0, current_price=10.0,
        growth=0.15, discount=0.10, terminal=0.03,
    )
    assert "error" in result
    assert "EPS" in result["error"]


def test_dcf_eps_negative_returns_error():
    from services.dcf import dcf_valuation

    result = dcf_valuation(
        eps=-0.5, current_price=10.0,
        growth=0.15, discount=0.10, terminal=0.03,
    )
    assert "error" in result


def test_dcf_discount_le_terminal_returns_error():
    """discount <= terminal → 永续模型分母为 0 或负, 必须返回错误 (Spec Scenario spec.md:39-42)"""
    from services.dcf import dcf_valuation

    result = dcf_valuation(
        eps=1.0, current_price=10.0,
        growth=0.15, discount=0.03, terminal=0.03,
    )
    assert "error" in result


def test_dcf_upside_pct_calculation():
    """current_price = 20, fair ≈ 24.4 → upside ≈ +22%"""
    from services.dcf import dcf_valuation

    result = dcf_valuation(
        eps=1.0, current_price=20.0,
        growth=0.15, discount=0.10, terminal=0.03,
    )
    # upside = (fair - 20) / 20 * 100
    expected = (result["fair_value_per_share"] - 20.0) / 20.0 * 100
    # 浮点 + round() 边界, 容差 0.02
    assert abs(result["upside_pct"] - round(expected, 2)) < 0.02


def test_dcf_current_price_zero_upside_is_none():
    """current_price = 0 → upside_pct 不能除零, 应为 None"""
    from services.dcf import dcf_valuation

    result = dcf_valuation(
        eps=1.0, current_price=0.0,
        growth=0.15, discount=0.10, terminal=0.03,
    )
    assert result["upside_pct"] is None