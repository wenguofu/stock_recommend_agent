"""TDD Red — K 线形态检测测试

覆盖 design.md detect_patterns() 契约:
  - 返回 [{date, type, direction, note}, ...]
  - 5 类: gap_up / gap_down / doji / upper_shadow / lower_shadow
  - 第一根无前置, 不检测
"""
import pytest


def test_gap_up_detected_when_today_low_above_prev_high():
    """今日 low > 昨 high * 1.01 → 跳空向上缺口"""
    from services.pattern_detect import detect_patterns

    klines = [
        {"date": "2025-01-01", "open": 10.0, "high": 10.5, "low": 9.5, "close": 10.2},
        {"date": "2025-01-02", "open": 11.0, "high": 11.5, "low": 10.8, "close": 11.3},
    ]
    patterns = detect_patterns(klines)
    types = [p["type"] for p in patterns]
    assert "gap_up" in types
    gap = next(p for p in patterns if p["type"] == "gap_up")
    assert gap["date"] == "2025-01-02"
    assert "跳空" in gap["note"]


def test_gap_down_detected_when_today_high_below_prev_low():
    """今日 high < 昨 low * 0.99 → 跳空向下缺口"""
    from services.pattern_detect import detect_patterns

    klines = [
        {"date": "2025-01-01", "open": 10.0, "high": 10.5, "low": 9.5, "close": 9.8},
        {"date": "2025-01-02", "open": 9.0, "high": 9.2, "low": 8.8, "close": 9.1},
    ]
    patterns = detect_patterns(klines)
    types = [p["type"] for p in patterns]
    assert "gap_down" in types


def test_doji_detected_when_body_small():
    """|close-open| / (high-low) < 0.1 → 十字星"""
    from services.pattern_detect import detect_patterns

    klines = [
        {"date": "2025-01-01", "open": 10.0, "high": 11.0, "low": 9.0, "close": 9.5},
        {"date": "2025-01-02", "open": 10.0, "high": 10.5, "low": 9.5, "close": 10.02},  # body 0.02 / range 1.0 = 0.02
    ]
    patterns = detect_patterns(klines)
    types = [p["type"] for p in patterns]
    assert "doji" in types


def test_upper_shadow_detected():
    """(high - max(open,close)) / (high-low) > 0.6 → 长上影"""
    from services.pattern_detect import detect_patterns

    klines = [
        {"date": "2025-01-01", "open": 10.0, "high": 11.0, "low": 9.0, "close": 9.5},
        {"date": "2025-01-02", "open": 10.0, "high": 13.0, "low": 9.5, "close": 10.5},  # upper = 2.5, range = 3.5, 0.71
    ]
    patterns = detect_patterns(klines)
    types = [p["type"] for p in patterns]
    assert "upper_shadow" in types


def test_lower_shadow_detected():
    """(min(open,close) - low) / (high-low) > 0.6 → 长下影"""
    from services.pattern_detect import detect_patterns

    klines = [
        {"date": "2025-01-01", "open": 10.0, "high": 11.0, "low": 9.0, "close": 9.5},
        {"date": "2025-01-02", "open": 10.0, "high": 10.5, "low": 7.0, "close": 10.3},  # lower = 3.3, range = 3.5, 0.94
    ]
    patterns = detect_patterns(klines)
    types = [p["type"] for p in patterns]
    assert "lower_shadow" in types


def test_first_kline_no_pattern():
    """第一根没有前置, 不应输出 pattern"""
    from services.pattern_detect import detect_patterns

    klines = [
        {"date": "2025-01-01", "open": 10.0, "high": 13.0, "low": 7.0, "close": 10.5},
    ]
    patterns = detect_patterns(klines)
    assert patterns == []


def test_empty_input_returns_empty():
    from services.pattern_detect import detect_patterns

    assert detect_patterns([]) == []


def test_normal_kline_no_pattern():
    """正常无任何形态的 K 线 → 不输出"""
    from services.pattern_detect import detect_patterns

    klines = [
        {"date": "2025-01-01", "open": 10.0, "high": 10.5, "low": 9.5, "close": 10.2},
        {"date": "2025-01-02", "open": 10.2, "high": 10.7, "low": 10.0, "close": 10.5},
    ]
    patterns = detect_patterns(klines)
    assert patterns == []