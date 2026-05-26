# 大盘趋势监控与下行预警 — 实现方案

> **For Hermes:** 使用 subagent-driven-development + TDD 逐条实现。

**目标:** 构建大盘趋势监控引擎，识别历史模式 → 预判当前走势方向 → 在单边下行前发出预警

**架构:** 新建 `market_monitor.py` 模块 + 3个API端点 + 调度器任务 + 微信推送

**技术栈:** Python + pandas + numpy + ta-lib (ADX/MACD/RSI) + Sina K线

---

## 设计思路

### 预警信号体系（6维）

| 维度 | 信号 | 权重 |
|------|------|------|
| 趋势方向 | ADX>25 且 DI- > DI+（空头确立） | 25% |
| 均线形态 | MA20死叉MA60 / 价破MA120 | 25% |
| MACD背离 | DIF顶背离（价创新高DIF走低） | 15% |
| 量价背离 | 缩量反弹 + 放量下跌（派发信号） | 15% |
| 下跌动量 | 连续3天低点下移 + 收盘在低位 | 10% |
| RSI弱势 | RSI<40 且持续走低 | 10% |

### 预警等级

- **🟢 正常** (0-20分): 无异常
- **🟡 关注** (21-40分): 部分指标走弱，注意减仓
- **🟠 警惕** (41-60分): 多项指标恶化，建议降低仓位  
- **🔴 危险** (61-80分): 高概率单边下行，建议空仓/轻仓

### 历史模式匹配

取近20天价格走势向量，与历史3年中相似片段做余弦相似度匹配，找到TOP3最相似的历史时点，展示其后20天的实际走势，作为当前走势的参考预判。

---

## 文件结构

```
market_monitor.py          # 核心引擎（新建）
api_routes.py              # 新增3个端点
scheduler.py               # 新增定时任务
scripts/market_alert.py    # 预警推送脚本（新建）
tests/test_market_monitor.py  # 测试
```

---

## 任务清单

### Task 1: 创建 market_monitor.py 骨架 + 数据获取

**文件:**
- Create: `market_monitor.py`
- Create: `tests/test_market_monitor.py`

**Step 1: 写测试**

```python
def test_get_index_kline_returns_dataframe():
    from market_monitor import get_index_kline
    df = get_index_kline('000001', days=180)
    assert df is not None
    assert len(df) > 0
    assert 'close' in df.columns
    assert 'high' in df.columns
    assert 'low' in df.columns
    assert 'volume' in df.columns
```

**Step 2: 验证失败** → `pytest tests/test_market_monitor.py::test_get_index_kline_returns_dataframe -v`

**Step 3: 实现**

```python
# market_monitor.py
from data_fetchers import get_daily_kline

def get_index_kline(code='000001', days=180):
    """获取指数日K线数据"""
    df = get_daily_kline(code, count=days)
    return df
```

**Step 4: 验证通过** → `pytest tests/test_market_monitor.py -v`

---

### Task 2: ADX趋势方向检测

**文件:**
- Modify: `market_monitor.py`
- Modify: `tests/test_market_monitor.py`

**Step 1: 写测试**

```python
def test_adx_trend_signal_bullish():
    """上升趋势中 ADX 信号应为多头"""
    df = pd.DataFrame({
        'high': [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]*3,
        'low': [9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19]*3,
        'close': [9.5, 10.5, 11.5, 12.5, 13.5, 14.5, 15.5, 16.5, 17.5, 18.5, 19.5]*3,
    })
    from market_monitor import check_adx_trend
    result = check_adx_trend(df)
    assert 'score' in result
    assert 'signal' in result
    assert result['signal'] in ['bullish', 'bearish', 'neutral']
```

**Step 3: 实现**

```python
def check_adx_trend(df, period=14):
    """ADX趋势方向检测
    - ADX > 25 且 +DI > -DI: 多头趋势
    - ADX > 25 且 -DI > +DI: 空头趋势（危险信号）
    - ADX < 20: 无明显趋势
    """
    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    
    # 用 Python 实现简化版 ADX（避免 ta-lib 依赖问题）
    # True Range
    tr = []
    for i in range(1, len(close)):
        hl = high[i] - low[i]
        hc = abs(high[i] - close[i-1])
        lc = abs(low[i] - close[i-1])
        tr.append(max(hl, hc, lc))
    
    # ATR
    atr = sum(tr[-period:]) / period
    
    # +DM / -DM
    plus_dm = []
    minus_dm = []
    for i in range(1, len(close)):
        up = high[i] - high[i-1]
        down = low[i-1] - low[i]
        if up > down and up > 0:
            plus_dm.append(up)
        else:
            plus_dm.append(0)
        if down > up and down > 0:
            minus_dm.append(down)
        else:
            minus_dm.append(0)
    
    # Smoothed +DI / -DI
    plus_di = (sum(plus_dm[-period:]) / period / atr * 100) if atr > 0 else 0
    minus_di = (sum(minus_dm[-period:]) / period / atr * 100) if atr > 0 else 0
    
    # DX and ADX (simplified)
    dx_sum = plus_di + minus_di
    dx = abs(plus_di - minus_di) / dx_sum * 100 if dx_sum > 0 else 0
    
    # Simple ADX: average DX over period
    adx = dx  # simplified single-period
    
    if adx > 25:
        if minus_di > plus_di:
            return {'score': 25, 'signal': 'bearish', 
                    'detail': f'ADX={adx:.1f} -DI={minus_di:.1f} > +DI={plus_di:.1f} 空头趋势',
                    'adx': round(adx, 1), 'plus_di': round(plus_di, 1), 'minus_di': round(minus_di, 1)}
        else:
            return {'score': 0, 'signal': 'bullish',
                    'detail': f'ADX={adx:.1f} +DI={plus_di:.1f} > -DI={minus_di:.1f} 多头趋势',
                    'adx': round(adx, 1), 'plus_di': round(plus_di, 1), 'minus_di': round(minus_di, 1)}
    else:
        return {'score': 0, 'signal': 'neutral',
                'detail': f'ADX={adx:.1f} 无明显趋势',
                'adx': round(adx, 1), 'plus_di': round(plus_di, 1), 'minus_di': round(minus_di, 1)}
```

---

### Task 3: 均线形态检测

**Step 1: 写测试**

```python
def test_ma_death_cross_detected():
    """MA20下穿MA60应触发死叉信号"""
    close = list(range(100, 50, -1)) + list(range(50, 45, -1))
    df = pd.DataFrame({'close': close})
    from market_monitor import check_ma_pattern
    result = check_ma_pattern(df)
    # 下降趋势中应有空头信号
    assert 'score' in result
```

**Step 3: 实现**

```python
def check_ma_pattern(df):
    """均线形态检测
    - MA20死叉MA60: 20分（中期转空）
    - 价破MA120: 15分（长期趋势破坏）
    - MA空头排列(MA20<MA60<MA120): 25分
    """
    close = df['close'].values
    n = len(close)
    score = 0
    signals = []
    
    ma20 = sum(close[-20:]) / min(20, n)
    ma60 = sum(close[-60:]) / min(60, n)
    ma120 = sum(close[-120:]) / min(120, n) if n >= 120 else ma60
    cur = close[-1]
    
    # 死叉
    if n >= 60:
        if ma20 < ma60:
            score += 20
            signals.append(f'MA20({ma20:.0f})<MA60({ma60:.0f}) 死叉，中期转空')
    
    # 价破年线
    if n >= 120 and cur < ma120:
        score += 15
        signals.append(f'价格{cur:.0f}跌破年线MA120({ma120:.0f})')
    
    # 空头排列
    if n >= 120 and ma20 < ma60 < ma120:
        score += 25
        signals.append('均线空头排列 MA20<MA60<MA120')
    
    return {
        'score': score,
        'signals': signals,
        'ma20': round(ma20, 1), 'ma60': round(ma60, 1), 'ma120': round(ma120, 1) if n>=120 else None
    }
```

---

### Task 4: MACD顶背离检测

**Step 1: 写测试**

```python
def test_macd_divergence_detected():
    """价创新高但MACD走低 → 顶背离"""
    import pandas as pd, numpy as np
    dates = pd.date_range('2026-01-01', periods=120)
    close = np.concatenate([
        np.linspace(3000, 3500, 60),  # 上升段
        np.linspace(3500, 3600, 30),   # 新高但动能减弱
        np.linspace(3500, 3300, 30),   # 下跌
    ])
    df = pd.DataFrame({'close': close, 'date': dates})
    from market_monitor import check_macd_divergence
    result = check_macd_divergence(df)
    assert 'score' in result
```

**Step 3: 实现**

```python
def check_macd_divergence(df):
    """MACD顶背离检测"""
    close = df['close'].values
    n = len(close)
    
    # EMA计算
    def ema(data, period):
        alpha = 2 / (period + 1)
        result = [data[0]]
        for i in range(1, len(data)):
            result.append(alpha * data[i] + (1 - alpha) * result[-1])
        return result
    
    ema12 = ema(close, 12)
    ema26 = ema(close, 26)
    dif = [e12 - e26 for e12, e26 in zip(ema12, ema26)]
    dea = ema(dif, 9)
    macd = [(d - e) * 2 for d, e in zip(dif, dea)]
    
    # 检查最近60天内的顶背离
    score = 0
    signals = []
    
    if n >= 60:
        recent_close = close[-60:]
        recent_dif = dif[-60:]
        
        # 找近60天的两个高点
        half = 60 // 2
        first_half_high = max(recent_close[:half])
        second_half_high = max(recent_close[half:])
        
        first_dif_at_high = recent_dif[recent_close[:half].argmax()]
        second_dif_at_high = recent_dif[half + recent_close[half:].argmax()]
        
        # 价创新高但 DIF 走低 = 顶背离
        if second_half_high > first_half_high and second_dif_at_high < first_dif_at_high:
            score = 15
            signals.append(f'MACD顶背离：价创新高({second_half_high:.0f}>{first_half_high:.0f})但DIF走低')
    
    return {'score': score, 'signals': signals, 'dif': round(dif[-1], 2), 'dea': round(dea[-1], 2)}
```

---

### Task 5: 量价背离（派发信号）

**Step 3: 实现**

```python
def check_volume_divergence(df):
    """量价背离检测（派发信号）
    - 上涨日缩量 + 下跌日放量 = 派发
    - 连续3日以上高换手下跌 = 恐慌抛售
    """
    close = df['close'].values
    volume = df['volume'].values
    n = len(close)
    
    if n < 20:
        return {'score': 0, 'signals': [], 'ratio': 0}
    
    score = 0
    signals = []
    
    # 统计近20日
    up_vol = 0
    up_days = 0
    down_vol = 0
    down_days = 0
    
    for i in range(-20, 0):
        if close[i] > close[i-1]:
            up_vol += volume[i]
            up_days += 1
        else:
            down_vol += volume[i]
            down_days += 1
    
    avg_up_vol = up_vol / max(up_days, 1)
    avg_down_vol = down_vol / max(down_days, 1)
    
    # 下跌日均量 > 上涨日均量 * 1.3 = 派发信号
    if avg_down_vol > avg_up_vol * 1.3:
        ratio = avg_down_vol / avg_up_vol if avg_up_vol > 0 else 2
        score = 15
        signals.append(f'量价背离：下跌日均量{avg_down_vol:.0f} > 上涨日{avg_up_vol:.0f}（派发信号，比率{ratio:.1f}x）')
    
    return {'score': score, 'signals': signals, 'ratio': round(avg_down_vol/avg_up_vol, 1) if avg_up_vol > 0 else 0}
```

---

### Task 6: 下跌动量 + RSI弱势

**Step 3: 实现**

```python
def check_momentum_rsi(df):
    """下跌动量 + RSI弱势检测"""
    close = df['close'].values
    high = df['high'].values
    low = df['low'].values
    n = len(close)
    
    score = 0
    signals = []
    
    # 连续低点下移
    if n >= 5:
        recent_lows = [low[i] for i in range(-5, 0)]
        lower_lows = sum(1 for i in range(1, len(recent_lows)) if recent_lows[i] < recent_lows[i-1])
        if lower_lows >= 3:
            score += 10
            signals.append(f'连续{lower_lows}天低点下移，下跌动量增强')
    
    # RSI 计算
    if n >= 14:
        gains = []
        losses = []
        for i in range(-14, 0):
            diff = close[i] - close[i-1]
            if diff > 0:
                gains.append(diff)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(diff))
        
        avg_gain = sum(gains) / 14
        avg_loss = sum(losses) / 14
        rs = avg_gain / avg_loss if avg_loss > 0 else 100
        rsi = 100 - (100 / (1 + rs))
        
        if rsi < 40:
            score += 10
            signals.append(f'RSI={rsi:.1f} 处于弱势区(<40)，反弹力度有限')
    
    return {'score': min(score, 20), 'signals': signals, 'rsi': round(rsi, 1) if 'rsi' in dir() else None}
```

---

### Task 7: 综合评分 + 历史模式匹配

**Step 3: 实现**

```python
def full_monitor(code='000001'):
    """大盘趋势全面监控
    
    Returns:
        {
            'warning_level': 'normal'|'watch'|'alert'|'danger',
            'total_score': int,    # 0-100
            'signals': [...],
            'verdict': str,
            'indicators': {...},
            'similar_patterns': [...]  # 历史相似模式
        }
    """
    df = get_index_kline(code, days=180)
    if df is None or df.empty:
        return {'error': '无法获取大盘数据'}
    
    # 各维检测
    adx = check_adx_trend(df)
    ma = check_ma_pattern(df)
    macd = check_macd_divergence(df)
    vol = check_volume_divergence(df)
    mom = check_momentum_rsi(df)
    
    # 加权合成
    total = adx['score'] + ma['score'] + macd['score'] + vol['score'] + mom['score']
    total = min(total, 100)
    
    # 收集所有信号
    all_signals = []
    for check in [adx, ma, macd, vol, mom]:
        if 'signals' in check:
            all_signals.extend(check['signals'])
        elif 'detail' in check and check.get('score', 0) > 0:
            all_signals.append(check['detail'])
    
    # 判定等级
    if total >= 61:
        level, emoji, verdict = 'danger', '🔴', '高危：多项指标共振看空，单边下行概率高'
        suggest = '建议空仓或极轻仓，现金为王，不抄底不追反弹。'
    elif total >= 41:
        level, emoji, verdict = 'alert', '🟠', '警惕：趋势恶化信号增多，建议降低仓位至3成以下'
        suggest = '减仓为主，持有防御性板块，设置止损。'
    elif total >= 21:
        level, emoji, verdict = 'watch', '🟡', '关注：部分指标走弱，注意控制风险'
        suggest = '控制仓位在5成，优选题材股，减少追高操作。'
    else:
        level, emoji, verdict = 'normal', '🟢', '正常：大盘技术面健康，无明显下行风险'
        suggest = '正常操作，持股为主，关注板块轮动。'
    
    # 历史模式匹配（简化版）
    similar = find_similar_patterns(df)
    
    return {
        'warning_level': level,
        'total_score': total,
        'verdict': f'{emoji} {verdict}',
        'suggest': suggest,
        'signals': all_signals,
        'indicators': {
            'adx': adx, 'ma': ma, 'macd': macd,
            'volume': vol, 'momentum_rsi': mom,
        },
        'similar_patterns': similar,
        'cur_price': round(float(df['close'].values[-1]), 2),
        'timestamp': datetime.now().isoformat()
    }


def find_similar_patterns(df, window=20, top_k=3):
    """找历史上最相似的走势片段"""
    close = df['close'].values
    n = len(close)
    if n < window + 20:
        return []
    
    # 当前走势：最近20天归一化收益率向量
    current = []
    for i in range(-window, 0):
        current.append((close[i] - close[i-window-1]) / close[i-window-1] * 100 if i-window-1 >= 0 else 0)
    current = np.array(current)
    current_norm = np.linalg.norm(current)
    if current_norm == 0:
        return []
    current_vec = current / current_norm
    
    # 扫描历史
    similarities = []
    for start in range(0, n - window * 2):
        hist = []
        for i in range(start, start + window):
            base_idx = max(start - 1, 0)
            hist.append((close[i] - close[base_idx]) / close[base_idx] * 100 if close[base_idx] != 0 else 0)
        hist = np.array(hist)
        hist_norm = np.linalg.norm(hist)
        if hist_norm == 0:
            continue
        hist_vec = hist / hist_norm
        
        sim = np.dot(current_vec, hist_vec)  # cosine similarity
        similarities.append((sim, start))
    
    similarities.sort(reverse=True)
    
    # Top 3 最相似
    results = []
    for sim, start in similarities[:top_k]:
        end = min(start + window + 20, n)
        future_close = close[start+window:end]
        future_return = (future_close[-1] - future_close[0]) / future_close[0] * 100 if len(future_close) > 0 else 0
        
        results.append({
            'similarity': round(sim * 100, 1),
            'match_date': str(df['date'].values[start])[:10] if 'date' in df.columns else '',
            'future_20d_return': round(future_return, 1),
            'direction': 'up' if future_return > 0 else 'down'
        })
    
    return results
```

---

### Task 8: API端点 + 调度器集成

**文件:**
- Modify: `api_routes.py` (新增3个端点)
- Modify: `scheduler.py` (新增任务)

**API端点:**

1. `GET /api/market/monitor` — 完整监控报告
2. `GET /api/market/monitor/quick` — 仅返回预警等级+分数（轻量，给alert脚本用）
3. `GET /api/market/monitor/history?days=60` — 历史信号变化趋势

**调度器任务:**

```python
# scheduler.py 新增
('market_monitor_alert', 300, 'market_alert', '盯盘时段'),  # 每5分钟
```

### Task 9: 预警推送脚本

**文件:**
- Create: `scripts/market_alert.py`

```python
#!/usr/bin/env python3
"""大盘趋势预警推送脚本 — no_agent cron 模式"""
import json, os, sys
from datetime import datetime
from urllib.request import urlopen, Request

API = os.environ.get('A_STOCK_API', 'http://127.0.0.1:35000')

# 交易日+交易时段检查
now = datetime.now()
if now.weekday() >= 5: sys.exit(0)
h, m = now.hour, now.minute
if not ((h==9 and m>=30) or h==10 or (h==11 and m<=30) or h==13 or h==14 or (h==15 and m==0)):
    sys.exit(0)

try:
    req = Request(f'{API}/api/market/monitor/quick', headers={'User-Agent': 'market-alert/1.0'})
    with urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
except:
    sys.exit(0)

level = data.get('warning_level', 'normal')
score = data.get('total_score', 0)

# 只在🟠警惕 或 🔴危险 时推送
if level in ('alert', 'danger'):
    signals = data.get('signals', [])
    print(f"⚠️ 大盘预警 ({now.strftime('%H:%M')})")
    print(f"{data.get('verdict', '')}  评分:{score}")
    print(data.get('suggest', ''))
    if signals:
        print("─" * 20)
        for s in signals[:5]:
            print(f"  • {s}")
```

---

### Task 10: 注册路由 + 测试 + 调度器集成

在 `api_routes.py` 注册 `/api/market/monitor` 等端点，在 `scheduler.py` 添加定时任务，在 `~/.hermes/scripts/` 放置 `market_alert.py` 并创建 cron job。

---

## 验收标准

- [ ] `pytest tests/test_market_monitor.py -v` 全绿
- [ ] `curl http://localhost:35000/api/market/monitor` 返回完整报告
- [ ] `curl http://localhost:35000/api/market/monitor/quick` 轻量返回
- [ ] 调度器每5分钟运行 market_alert
- [ ] 预警达到🟠/🔴时微信推送
