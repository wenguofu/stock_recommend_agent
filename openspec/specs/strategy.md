# Strategy — 策略回测与选股

## 策略推荐 (3 Tab)

| Tab | API | 逻辑 |
|-----|-----|------|
| 强势股接力 | `/api/strategy/strong_stocks` | T-1/T-2涨停未连板 |
| 十倍潜力股 | `/api/strategy/tenbagger` | ROE>5% + 毛利>20% + 技术面 |
| 突破形态 | `/api/strategy/breakout` | 突破20日高点+放量+站上MA20 |

统一推荐：`/api/strategy/recommendations`

## 回测引擎 (backtest_engine.py, 27.8KB)

4 种内置策略：

| 策略 | 函数 | 信号 |
|------|------|------|
| 均线金叉 | `generate_signals(ma_cross)` | 快线上穿买/下穿卖 |
| RSI 反转 | `generate_signals(rsi_reversal)` | RSI<30买/>70卖 |
| MACD | `generate_signals(macd_cross)` | DIF上穿买/下穿卖 |
| 布林带 | `generate_signals(bollinger_break)` | 跌破下轨买/突破上轨卖 |

### 交易模拟

- 信号次日开盘执行（防未来函数）
- 全仓买入（100股倍数）
- 佣金万2.5(最低5元) + 卖出印花税千1

### 输出指标

总收益率、年化收益、最大回撤、夏普比率、胜率、交易次数、买入持有基准

## 择时过滤器

基于 ADX + 波动率过滤弱信号，PF=1.32 (全市场) / PF=1.64 (主线股)

### API 端点

| 端点 | 用途 |
|------|------|
| `POST /api/backtest/run` | 单策略回测 |
| `POST /api/strategy/batch_backtest` | 批量回测 |
| `POST /api/strategy/grid_search` | 参数网格搜索 |
| `POST /api/forecast` | 5场景预测 |

## 预测模型 (forecast)

确定性趋势 + 均匀噪声模型（非 GBM）。

### 已知问题

- [ ] 回测无滑点模拟
- [ ] 择时过滤阈值硬编码（ADX 25-50, 波动 18-50%）
- [ ] `strategy_engine.py` 与 `backtest_engine.py` 职责重叠
