# Tasks — Market Trend Monitor

> TDD: 每个 Task = RED(写测试→验证失败) → GREEN(最小实现→验证通过) → REFACTOR

---

### Task 1: 创建 market_monitor.py 骨架

**RED** — Write test:
- [ ] `test_get_index_kline_returns_dataframe` — 调用返回 DataFrame
- [ ] `test_get_index_kline_default_code` — 默认代码 sh000001

**GREEN** — Implement `get_index_kline()`:
- [ ] 导入 `data_fetchers.get_daily_kline`
- [ ] 默认参数 `code='sh000001', days=180`

---

### Task 2: EMA 工具函数

**RED** — Write test:
- [ ] `test_ema_basic` — 基本EMA计算正确性
- [ ] `test_ema_short_data` — 数据不足period时返回NaN数组

**GREEN** — Implement `_ema()`:
- [ ] Wilder's smoothing: seed=SMA, multiplier=2/(period+1)

---

### Task 3: ADX趋势检测

**RED** — Write test:
- [ ] `test_adx_trend_bearish` — 下降趋势中 score=25, signal='bearish'
- [ ] `test_adx_trend_bullish` — 上升趋势中 score=0, signal='bullish'
- [ ] `test_adx_trend_neutral_low_adx` — ADX≤25 返回 neutral

**GREEN** — Implement `check_adx_trend()`:
- [ ] TR, +DM, -DM 计算
- [ ] Wilder's smoothing (ATR, +DI, -DI, ADX)
- [ ] Period=14, 阈值 ADX=25

---

### Task 4: 均线形态检测

**RED** — Write test:
- [ ] `test_ma_death_cross` — MA20<MA60 → score≥20
- [ ] `test_ma_below_ma120` — 价跌破MA120 → score≥15
- [ ] `test_ma_bearish_alignment` — 空头排列 → score=25
- [ ] `test_ma_bullish` — 多头排列 → score=0

**GREEN** — Implement `check_ma_pattern()`:
- [ ] SMA(20/60/120)
- [ ] 死叉/价破年线/空头排列 检测

---

### Task 5: MACD顶背离

**RED** — Write test:
- [ ] `test_macd_divergence_detected` — 价创新高+DIF走低 → score=15
- [ ] `test_macd_no_divergence` — 正常情况 → score=0

**GREEN** — Implement `check_macd_divergence()`:
- [ ] EMA(12/26) → DIF, EMA(9) → DEA
- [ ] 60天窗口顶背离检测

---

### Task 6: 量价背离

**RED** — Write test:
- [ ] `test_volume_divergence_detected` — 下跌均量>上涨均量×1.3 → score=15
- [ ] `test_volume_normal` — 正常量价 → score=0

**GREEN** — Implement `check_volume_divergence()`:
- [ ] 近20日升跌分类统计
- [ ] 比率计算

---

### Task 7: 下跌动量+RSI

**RED** — Write test:
- [ ] `test_momentum_lower_lows` — ≥3天低点下移 → score≥10
- [ ] `test_rsi_weak` — RSI<40 → score≥10
- [ ] `test_rsi_normal` — RSI≥40 → rsi部分score=0

**GREEN** — Implement `check_momentum_rsi()`:
- [ ] 低点下移计数
- [ ] RSI(14) 纯Python实现

---

### Task 8: 历史相似模式匹配

**RED** — Write test:
- [ ] `test_similar_patterns_returns_list` — 返回非空列表
- [ ] `test_similar_patterns_insufficient_data` — 数据不足 → 空列表

**GREEN** — Implement `find_similar_patterns()`:
- [ ] 20日归一化收益向量
- [ ] 余弦相似度扫描
- [ ] TOP3排序

---

### Task 9: 综合评分 full_monitor()

**RED** — Write test:
- [ ] `test_full_monitor_returns_correct_structure` — 包含所有必需字段
- [ ] `test_full_monitor_normal_market` — 健康市场 → warning_level='normal'
- [ ] `test_full_monitor_danger_market` — 恶化市场 → warning_level='danger'
- [ ] `test_full_monitor_empty_df` — 空数据 → error

**GREEN** — Implement `full_monitor()`:
- [ ] 聚合6维检测
- [ ] 总分 → 等级映射
- [ ] 返回完整报告dict

---

### Task 10: API端点注册

- [ ] `GET /api/market/monitor` → 调用 `full_monitor()`
- [ ] `GET /api/market/monitor/quick` → 轻量返回
- [ ] `GET /api/market/monitor/history` → 维度分数明细
- [ ] 在 `api_routes.py` 注册

### Task 11: 调度器 + 推送脚本

- [ ] `scheduler.py` 新增 `task_market_monitor`（每5分钟）
- [ ] `scripts/market_alert.py` — 仅🟠/🔴推送
- [ ] 复制到 `~/.hermes/scripts/`

### Task 12: OpenSpec 验证 + 真实数据验证

- [ ] `openspec validate market-trend-monitor`
- [ ] `curl /api/market/monitor` 返回真实大盘数据
- [ ] 31个测试全绿
