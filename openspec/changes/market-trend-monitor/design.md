# Market Trend Monitor — 大盘趋势监控

> OpenSpec: spec-driven | TDD: RED→GREEN→REFACTOR

## Purpose

实时监控A股大盘指数（上证sh000001）的技术面趋势，通过多维度量化指标识别恶化信号，在单边下行发生前发出分级预警。

## Architecture

```
market_monitor.py         # 核心引擎（纯Python+numpy，不依赖ta-lib）
  ├── get_index_kline()   # 获取指数日K线（复用data_fetchers）
  ├── check_market_breadth() # 🆕 市场宽度（涨跌停家数）— 硬性标准
  ├── check_adx_trend()   # ADX趋势方向检测
  ├── check_ma_pattern()  # 均线形态检测
  ├── check_macd_divergence()  # MACD顶背离检测
  ├── check_volume_divergence() # 量价背离检测
  ├── check_momentum_rsi()  # 下跌动量+RSI弱势检测
  ├── find_similar_patterns() # 历史相似模式匹配
  └── full_monitor()      # 综合评分+预警等级

api_routes.py             # 3个API端点
scheduler.py              # 定时任务（每5分钟）
scripts/market_alert.py   # no_agent推送脚本
```

## Behavior Requirements

### B0: 市场宽度 — 硬性标准（权重25%）
- 🆕 数据源: AKShare `stock_zt_pool_em(date)` 涨停池 + `stock_zt_pool_dtgc_em(date)` 跌停池
- 非交易时段 → 使用最近交易日数据，score=0（宽度只在盘中有效）
- 条件1: 跌停家数 > 50 → score += 15
- 条件2: 涨停家数 < 50 → score += 15
- 双条件同时触发 → score = 25（封顶）
- 返回: `{score, signals[], limit_up_count, limit_down_count, date}`

### B1: 数据获取
- `get_index_kline(code, days)` 调用 `data_fetchers.get_daily_kline()`
- 默认 `code='sh000001'`（上证指数），`days=180`

### B2: ADX趋势方向（权重25%）
- 输入: DataFrame with [high, low, close]
- 纯Python实现ADX/+DI/-DI（Wilder's smoothing，period=14）
- ADX > 25 且 -DI > +DI → score=25, signal='bearish'
- ADX > 25 且 +DI > -DI → score=0, signal='bullish'
- ADX ≤ 25 → score=0, signal='neutral'
- 返回: `{score, signal, detail, adx, plus_di, minus_di}`

### B3: 均线形态（权重25%）
- MA20死叉MA60 → score+=20
- 收盘价跌破MA120 → score+=15
- MA20<MA60<MA120空头排列 → score+=25（最高）
- 返回: `{score, signals[], ma20, ma60, ma120}`

### B4: MACD顶背离（权重15%）
- 纯Python实现EMA(12/26/9)计算MACD
- 检测：近60天内，价格创新高但DIF走低
- 触发 → score=15
- 返回: `{score, signals[], dif, dea}`

### B5: 量价背离（权重15%）
- 近20日：下跌日均量 > 上涨日均量 × 1.3
- 触发 → score=15
- 返回: `{score, signals[], ratio}`

### B6: 下跌动量+RSI（权重10%+10%）
- 近5日≥3天低点下移 → score+=10
- RSI(14) < 40 → score+=10
- 返回: `{score, signals[], rsi}`

### B7: 历史相似模式匹配
- 取近20日归一化收益率向量
- 与历史窗口做余弦相似度匹配
- 返回TOP3: `[{similarity, match_date, future_20d_return, direction}]`

### B8: 综合评分
- 总分 = sum(各维度score)，上限100
- 映射预警等级：

| Score | Level | 含义 |
|-------|-------|------|
| 0-20 | normal | 🟢 正常 |
| 21-40 | watch | 🟡 关注 |
| 41-60 | alert | 🟠 警惕 |
| 61-100 | danger | 🔴 危险 |

### B9: API端点
- `GET /api/market/monitor` — 完整报告
- `GET /api/market/monitor/quick` — 轻量（仅等级+分数+信号）
- `GET /api/market/monitor/history` — 各维度分数明细

### B10: 推送规则
- 调度器每5分钟调用 quick API
- 仅 🟠alert 或 🔴danger 时推送微信
- 正常/关注时静默

## Data Contract

### full_monitor() 返回格式
```json
{
  "code": "sh000001",
  "warning_level": "normal|watch|alert|danger",
  "total_score": 35,
  "verdict": "注意风险",
  "suggest": "部分指标转弱...",
  "signals": ["[ma_pattern] 收盘价 < MA120..."],
  "checks": {
    "adx_trend": {"score": 0, "signal": "neutral", ...},
    "ma_pattern": {"score": 15, "signals": [...], ...},
    ...
  },
  "similar_patterns": [...],
  "cur_price": 4143.97,
  "timestamp": "2026-05-26T14:00:00"
}
```

## Edge Cases

- DataFrame为空或None → 返回 `{"error": "无法获取大盘数据"}`
- 数据不足14行（RSI）→ RSI返回None，该维度score=0
- 数据不足60行（MA60）→ 跳过MA60/MA120检测
- 数据不足120行（MA120）→ 跳过MA120检测
- 数据不足window+20 → 历史匹配返回空列表
- 非交易时段 → 调度器跳过，不执行

## Non-Requirements

- 不实现MACD底背离（仅做顶背离预警）
- 不实现多指数同时监控（仅上证sh000001）
- 不存储历史预警记录到DB（后续迭代）
- 不依赖ta-lib库
