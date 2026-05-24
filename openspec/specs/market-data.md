# Market Data — 行情数据层

## data_fetchers.py (76KB)

统一数据获取层，封装多个数据源：

| 函数 | 数据源 | 返回 |
|------|--------|------|
| `get_realtime_data(code)` | 腾讯 qt.gtimg.cn | 实时行情 dict |
| `get_daily_kline(code, count)` | kline_cache → Sina 兜底 | [{day,open,high,low,close,volume}] |
| `get_money_flow(code)` | Sina | 当日资金流向 |
| `get_money_flow_history(code, days)` | Sina | 历史资金流向 |
| `get_fundamental_data(code)` | akshare → stock_financials 表 | 财报数据 |
| `get_industry_comparison(code)` | 东方财富 | 行业对比 |

### 数据源特性

| 数据源 | 可用时段 | 限流 |
|--------|----------|------|
| 腾讯 qt.gtimg.cn | 24小时 | 50只/批 + 0.5s间隔 |
| Sina API | 交易时段为主 | HTTP 456 限流 ~2000次 |
| 东方财富/akshare | 仅交易时段 | 非交易时段挂死 |
| yfinance (美股) | 24小时 | Too Many Requests 偶发 |

### 腾讯 API 字段索引 (qt.gtimg.cn)

```
parts[3]=price [4]=yclose [33]=high [34]=low [37]=amount(万) [38]=turnover(%) [39]=pe [44]=mc(亿)
```

## technical_indicators.py

计算 MA/EMA/MACD/RSI/KDJ/BOLL/OBV，输出到 `get_comprehensive_data_with_indicators()`。

## data_formatters.py

将原始数据格式化为 AI prompt 可用的文本格式：`format_for_ai()`, `to_json()`。

## batch_prefetch_all.py (19.5KB)

全市场数据预取脚本。进度记录在 `.batch_prefetch_progress.json`。

### 已知问题

- [ ] Sina API Python 3.11 不兼容（`urlopen(headers={})` → 需 `Request(url, headers={})`）
- [ ] 腾讯 API 单请求获取多只股票（`qt.gtimg.cn/q=sh600150,sz300679`）可优化批处理效率
- [ ] `get_money_flow` 和 `get_daily_kline` 无统一缓存策略
