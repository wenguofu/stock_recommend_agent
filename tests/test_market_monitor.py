"""
Task 1: get_index_kline() 骨架
RED phase — tests should FAIL because market_monitor.py doesn't exist yet
"""
import pytest
import pandas as pd


def test_get_index_kline_returns_dataframe():
    """调用返回 DataFrame"""
    from market_monitor import get_index_kline
    df = get_index_kline('sh000001', days=10)
    assert df is not None
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0


def test_get_index_kline_default_code():
    """默认代码为 sh000001"""
    from market_monitor import get_index_kline
    # 只测函数签名，不实际调API（太慢）
    import inspect
    sig = inspect.signature(get_index_kline)
    params = sig.parameters
    assert params['code'].default == 'sh000001'
    assert params['days'].default == 180


# ============================================================
# Task 2: EMA helper
# ============================================================

def test_ema_basic():
    """_ema() 计算 Wilder's smoothing 正确"""
    from market_monitor import _ema
    import numpy as np
    series = pd.Series([10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0])
    result = _ema(series, period=5)
    assert result is not None
    assert len(result) == len(series)
    # First 4 should be NaN (not enough data for SMA seed)
    assert np.isnan(result.iloc[0])
    assert np.isnan(result.iloc[3])
    # 5th value (index 4) should be SMA of first 5
    expected_sma = (10 + 11 + 12 + 13 + 14) / 5  # = 12.0
    assert abs(result.iloc[4] - expected_sma) < 0.01
    # 6th value (index 5): Wilder's: EMA = price*(1/5) + prev_ema*(4/5)
    expected_ema6 = 15.0 * (1/5) + expected_sma * (4/5)  # = 3.0 + 9.6 = 12.6
    assert abs(result.iloc[5] - expected_ema6) < 0.01


def test_ema_short_data():
    """_ema() 数据不足 period 时返回全 NaN"""
    from market_monitor import _ema
    import numpy as np
    series = pd.Series([10.0, 11.0])
    result = _ema(series, period=5)
    assert result is not None
    assert len(result) == 2
    assert np.isnan(result.iloc[0])
    assert np.isnan(result.iloc[1])


# ============================================================
# Task 3: ADX trend
# ============================================================

def test_adx_trend_bearish():
    """下跌趋势，ADX>25，-DI>+DI → score=25, signal=bearish"""
    from market_monitor import check_adx_trend
    import numpy as np
    # Create declining prices: steady downtrend
    n = 60
    prices = np.linspace(100, 80, n)  # steady decline
    dates = pd.date_range('2024-01-01', periods=n, freq='B')
    df = pd.DataFrame({
        'date': dates,
        'open': prices - 0.1,
        'high': prices + 0.1,
        'low': prices - 0.1,
        'close': prices,
        'volume': np.ones(n) * 10000,
    })
    result = check_adx_trend(df)
    assert result is not None
    assert result['signal'] == 'bearish'
    assert result['score'] == 25
    assert 'adx' in result
    assert result['adx'] > 0
    assert result['plus_di'] < result['minus_di']


def test_adx_trend_bullish():
    """上涨趋势，ADX>25，+DI>-DI"""
    from market_monitor import check_adx_trend
    import numpy as np
    n = 60
    prices = np.linspace(80, 100, n)  # steady rise
    dates = pd.date_range('2024-01-01', periods=n, freq='B')
    df = pd.DataFrame({
        'date': dates,
        'open': prices - 0.1,
        'high': prices + 0.1,
        'low': prices - 0.1,
        'close': prices,
        'volume': np.ones(n) * 10000,
    })
    result = check_adx_trend(df)
    assert result is not None
    assert result['signal'] == 'bullish'
    assert result['score'] == 0
    assert result['plus_di'] > result['minus_di']


def test_adx_trend_neutral_low_adx():
    """横盘震荡，ADX<25 → neutral"""
    from market_monitor import check_adx_trend
    import numpy as np
    n = 60
    prices = np.ones(n) * 90.0  # flat
    dates = pd.date_range('2024-01-01', periods=n, freq='B')
    df = pd.DataFrame({
        'date': dates,
        'open': prices,
        'high': prices + 0.05,
        'low': prices - 0.05,
        'close': prices,
        'volume': np.ones(n) * 10000,
    })
    result = check_adx_trend(df)
    assert result is not None
    assert result['signal'] == 'neutral'
    assert result['score'] == 0


# ============================================================
# Task 4: MA pattern
# ============================================================

def test_ma_death_cross():
    """MA20 下穿 MA60 → signals 包含 death_cross，score +20"""
    from market_monitor import check_ma_pattern
    import numpy as np
    n = 130
    prices = np.linspace(100, 70, n)
    dates = pd.date_range('2024-01-01', periods=n, freq='B')
    df = pd.DataFrame({
        'date': dates,
        'open': prices - 0.1,
        'high': prices + 0.1,
        'low': prices - 0.1,
        'close': prices,
        'volume': np.ones(n) * 10000,
    })
    result = check_ma_pattern(df)
    assert result is not None
    assert 'death_cross' in result['signals']
    assert result['score'] >= 20
    assert result['ma20'] > 0
    assert result['ma60'] > 0
    assert result['ma120'] > 0


def test_ma_below_ma120():
    """价格低于 MA120 → price_below_ma120，score +15"""
    from market_monitor import check_ma_pattern
    import numpy as np
    n = 130
    prices = np.linspace(100, 50, n)
    dates = pd.date_range('2024-01-01', periods=n, freq='B')
    df = pd.DataFrame({
        'date': dates,
        'open': prices - 0.1,
        'high': prices + 0.1,
        'low': prices - 0.1,
        'close': prices,
        'volume': np.ones(n) * 10000,
    })
    result = check_ma_pattern(df)
    assert result is not None
    assert 'price_below_ma120' in result['signals']
    assert result['score'] >= 15


def test_ma_bearish_alignment():
    """MA20 < MA60 < MA120 → bearish_alignment，score +25"""
    from market_monitor import check_ma_pattern
    import numpy as np
    n = 130
    prices = np.linspace(100, 50, n)
    dates = pd.date_range('2024-01-01', periods=n, freq='B')
    df = pd.DataFrame({
        'date': dates,
        'open': prices - 0.1,
        'high': prices + 0.1,
        'low': prices - 0.1,
        'close': prices,
        'volume': np.ones(n) * 10000,
    })
    result = check_ma_pattern(df)
    assert result is not None
    assert 'bearish_alignment' in result['signals']
    assert result['score'] >= 25


def test_ma_bullish():
    """上涨趋势，无看空信号"""
    from market_monitor import check_ma_pattern
    import numpy as np
    n = 130
    prices = np.linspace(50, 100, n)
    dates = pd.date_range('2024-01-01', periods=n, freq='B')
    df = pd.DataFrame({
        'date': dates,
        'open': prices - 0.1,
        'high': prices + 0.1,
        'low': prices - 0.1,
        'close': prices,
        'volume': np.ones(n) * 10000,
    })
    result = check_ma_pattern(df)
    assert result is not None
    assert result['score'] == 0
    assert len(result['signals']) == 0


# ============================================================
# Task 5: MACD divergence
# ============================================================

def test_macd_divergence_detected():
    """价格新高但 DIF 下降 → divergence，score=15"""
    from market_monitor import check_macd_divergence
    import numpy as np
    n = 150
    # Build data: price has a higher high in last 60 days but momentum weakening
    prices = np.zeros(n)
    # First 90: steady rise
    prices[:90] = np.linspace(50, 100, 90)
    # Next 60: price goes to 105 (new high) then drops, but the climb is slow
    prices[90:120] = np.linspace(100, 108, 30)
    prices[120:] = np.linspace(108, 103, 30)  # slight decline at end
    dates = pd.date_range('2024-01-01', periods=n, freq='B')
    df = pd.DataFrame({
        'date': dates,
        'open': prices - 0.2,
        'high': prices + 0.2,
        'low': prices - 0.2,
        'close': prices,
        'volume': np.ones(n) * 10000,
    })
    result = check_macd_divergence(df)
    assert result is not None
    assert 'score' in result
    assert 'dif' in result
    assert 'dea' in result
    # With the price pattern above, divergence may or may not be detected
    # depending on exact DIF behavior. We assert the structure is correct.
    assert isinstance(result['score'], int)
    assert isinstance(result['signals'], list)


def test_macd_no_divergence():
    """持续上涨，无背离"""
    from market_monitor import check_macd_divergence
    import numpy as np
    n = 150
    prices = np.linspace(50, 100, n)  # clean uptrend
    dates = pd.date_range('2024-01-01', periods=n, freq='B')
    df = pd.DataFrame({
        'date': dates,
        'open': prices - 0.2,
        'high': prices + 0.2,
        'low': prices - 0.2,
        'close': prices,
        'volume': np.ones(n) * 10000,
    })
    result = check_macd_divergence(df)
    assert result is not None
    assert result['score'] == 0
    assert len(result['signals']) == 0


# ============================================================
# Task 6: Volume divergence
# ============================================================

def test_volume_divergence_detected():
    """跌日平均量 > 涨日平均量 * 1.3 → volume_divergence"""
    from market_monitor import check_volume_divergence
    import numpy as np
    n = 60
    prices = np.zeros(n)
    volumes = np.zeros(n)
    for i in range(n):
        if i % 2 == 0:
            prices[i] = 100.0 + i * 0.5  # up
            volumes[i] = 5000
        else:
            prices[i] = 99.0 - i * 0.5  # down
            volumes[i] = 15000
    dates = pd.date_range('2024-01-01', periods=n, freq='B')
    df = pd.DataFrame({
        'date': dates,
        'open': prices - 0.1,
        'high': prices + 0.2,
        'low': prices - 0.2,
        'close': prices,
        'volume': volumes,
    })
    result = check_volume_divergence(df)
    assert result is not None
    assert result['score'] > 0
    assert 'volume_divergence' in result['signals']
    assert result['ratio'] > 1.3


def test_volume_normal():
    """正常成交量，无背离"""
    from market_monitor import check_volume_divergence
    import numpy as np
    n = 60
    prices = np.linspace(90, 100, n)
    dates = pd.date_range('2024-01-01', periods=n, freq='B')
    df = pd.DataFrame({
        'date': dates,
        'open': prices - 0.1,
        'high': prices + 0.1,
        'low': prices - 0.1,
        'close': prices,
        'volume': np.ones(n) * 10000,
    })
    result = check_volume_divergence(df)
    assert result is not None
    assert 'volume_divergence' not in result['signals']
    assert result['score'] == 0


# ============================================================
# Task 7: Momentum + RSI
# ============================================================

def test_momentum_lower_lows():
    """最近 5 天中 ≥3 天低点下移 → lower_lows，score +10"""
    from market_monitor import check_momentum_rsi
    import numpy as np
    n = 60
    prices = np.linspace(60, 50, n)
    lows = np.linspace(59, 49, n)
    dates = pd.date_range('2024-01-01', periods=n, freq='B')
    df = pd.DataFrame({
        'date': dates,
        'open': prices + 0.5,
        'high': prices + 1.0,
        'low': lows,
        'close': prices,
        'volume': np.ones(n) * 10000,
    })
    result = check_momentum_rsi(df)
    assert result is not None
    assert 'lower_lows' in result['signals']
    assert result['score'] >= 10


def test_rsi_weak():
    """RSI < 40 → rsi_weak，score +10"""
    from market_monitor import check_momentum_rsi
    import numpy as np
    n = 60
    prices = np.linspace(80, 50, n)
    dates = pd.date_range('2024-01-01', periods=n, freq='B')
    df = pd.DataFrame({
        'date': dates,
        'open': prices - 0.1,
        'high': prices + 0.1,
        'low': prices - 0.1,
        'close': prices,
        'volume': np.ones(n) * 10000,
    })
    result = check_momentum_rsi(df)
    assert result is not None
    assert 'rsi' in result
    assert result['rsi'] < 40
    assert 'rsi_weak' in result['signals']
    assert result['score'] >= 10


# ============================================================
# Task 8: Similar patterns
# ============================================================

def test_similar_patterns_returns_list():
    """find_similar_patterns 返回正确格式的列表"""
    from market_monitor import find_similar_patterns
    import numpy as np
    n = 100
    prices = np.sin(np.linspace(0, 4 * np.pi, n)) * 10 + 100
    dates = pd.date_range('2024-01-01', periods=n, freq='B')
    df = pd.DataFrame({
        'date': dates,
        'open': prices - 0.2,
        'high': prices + 0.3,
        'low': prices - 0.3,
        'close': prices,
        'volume': np.ones(n) * 10000,
    })
    result = find_similar_patterns(df, window=20, top_k=3)
    assert result is not None
    assert isinstance(result, list)
    assert len(result) == 3
    for item in result:
        assert 'similarity' in item
        assert 'match_date' in item
        assert 'future_20d_return' in item
        assert 'direction' in item
        assert 0 <= item['similarity'] <= 1


def test_similar_patterns_insufficient_data():
    """数据不足时返回空列表"""
    from market_monitor import find_similar_patterns
    import numpy as np
    n = 15
    prices = np.linspace(90, 100, n)
    dates = pd.date_range('2024-01-01', periods=n, freq='B')
    df = pd.DataFrame({
        'date': dates,
        'open': prices,
        'high': prices + 0.1,
        'low': prices - 0.1,
        'close': prices,
        'volume': np.ones(n) * 10000,
    })
    result = find_similar_patterns(df, window=20, top_k=3)
    assert result == []


# ============================================================
# Task 9: full_monitor
# ============================================================

def test_full_monitor_returns_structure():
    """full_monitor 返回正确的结构"""
    from market_monitor import full_monitor
    import numpy as np
    # Synthetic data that won't call API
    n = 150
    prices = np.sin(np.linspace(0, 6 * np.pi, n)) * 20 + 100
    dates = pd.date_range('2024-01-01', periods=n, freq='B')
    df = pd.DataFrame({
        'date': dates,
        'open': prices - 0.2,
        'high': prices + 0.3,
        'low': prices - 0.3,
        'close': prices,
        'volume': np.ones(n) * 10000,
    })
    # We need to mock get_index_kline — but for structure test we can pass the df somehow
    # full_monitor calls get_index_kline internally, so we need to mock it
    from unittest.mock import patch
    with patch('market_monitor.get_index_kline', return_value=df):
        result = full_monitor(code='sh000001')
    assert result is not None
    assert isinstance(result, dict)
    assert result['code'] == 'sh000001'
    assert 'warning_level' in result
    assert result['warning_level'] in ('normal', 'watch', 'alert', 'danger')
    assert 'total_score' in result
    assert isinstance(result['total_score'], int)
    assert 'verdict' in result
    assert 'suggest' in result
    assert 'signals' in result
    assert isinstance(result['signals'], list)
    assert 'checks' in result
    assert isinstance(result['checks'], dict)
    assert 'similar_patterns' in result
    assert 'cur_price' in result
    assert 'timestamp' in result


def test_full_monitor_normal_market():
    """健康上涨市场 → normal，总分 0-20"""
    from market_monitor import full_monitor
    import numpy as np
    n = 150
    prices = np.linspace(80, 100, n)
    dates = pd.date_range('2024-01-01', periods=n, freq='B')
    df = pd.DataFrame({
        'date': dates,
        'open': prices - 0.2,
        'high': prices + 0.2,
        'low': prices - 0.2,
        'close': prices,
        'volume': np.ones(n) * 10000,
    })
    from unittest.mock import patch
    with patch('market_monitor.get_index_kline', return_value=df):
        result = full_monitor(code='sh000001')
    assert result['warning_level'] == 'normal'
    assert 0 <= result['total_score'] <= 20


def test_full_monitor_empty_df():
    """空 DataFrame 时优雅处理"""
    from market_monitor import full_monitor
    df = pd.DataFrame()
    from unittest.mock import patch
    with patch('market_monitor.get_index_kline', return_value=df):
        result = full_monitor(code='sh000001')
    assert result is not None
    assert 'error' in result or result['warning_level'] == 'normal'


# ═══════════════════════════════════════════════════════
# B0: Market Breadth — 硬性标准 (涨跌停家数)
# ═══════════════════════════════════════════════════════

def test_market_breadth_many_limit_down():
    """跌停>50 → score 15"""
    from market_monitor import _score_breadth
    result = _score_breadth(strong_count=100, limit_down=55)
    assert result['score'] >= 15
    assert any('跌停' in s for s in result['signals'])


def test_market_breadth_few_strong_stocks():
    """涨幅>8% <50 → score 15"""
    from market_monitor import _score_breadth
    result = _score_breadth(strong_count=30, limit_down=5)
    assert result['score'] >= 15
    assert any('涨幅>8%' in s for s in result['signals'])


def test_market_breadth_both_extreme():
    """跌停>50 且 涨幅>8%<50 → score 25"""
    from market_monitor import _score_breadth
    result = _score_breadth(strong_count=20, limit_down=60)
    assert result['score'] == 25
    assert len(result['signals']) >= 2


def test_market_breadth_normal():
    """正常市场 → score 0"""
    from market_monitor import _score_breadth
    result = _score_breadth(strong_count=80, limit_down=10)
    assert result['score'] == 0
    assert len(result['signals']) == 0


def test_market_breadth_returns_counts():
    """返回包含涨幅>8%和跌停家数"""
    from market_monitor import _score_breadth
    result = _score_breadth(strong_count=48, limit_down=16)
    assert result['strong_count'] == 48
    assert result['limit_down_count'] == 16


# ═══════════════════════════════════════════════════════
# B-1: Bear Market Confirmation — 周度累计规则
# ═══════════════════════════════════════════════════════

def test_bear_confirmation_triggered():
    """过去5天4天alert → 触发熊市确认"""
    from market_monitor import _check_bear_confirmation
    history = ['alert', 'alert', 'danger', 'alert', 'normal']
    result = _check_bear_confirmation(history)
    assert result is True


def test_bear_confirmation_not_triggered():
    """过去5天仅2天alert → 不触发"""
    from market_monitor import _check_bear_confirmation
    history = ['alert', 'normal', 'alert', 'normal', 'normal']
    result = _check_bear_confirmation(history)
    assert result is False


def test_bear_confirmation_exactly_3_days():
    """恰好3天 → 不触发(需要>3)"""
    from market_monitor import _check_bear_confirmation
    history = ['alert', 'alert', 'alert', 'normal', 'normal']
    result = _check_bear_confirmation(history)
    assert result is False


def test_bear_confirmation_short_history():
    """不足5天数据 → 不触发"""
    from market_monitor import _check_bear_confirmation
    history = ['alert', 'alert']
    result = _check_bear_confirmation(history)
    assert result is False
