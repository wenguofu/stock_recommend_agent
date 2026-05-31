# Market Data — 行情数据层

## data_fetchers.py (76KB)

统一数据获取层，封装多个数据源：

| 函数 | 数据源 | 返回 |
|------|--------|------|
| `get_realtime_data(code)` | 腾讯 qt.gtimg.cn | 实时行情 dict |
| `get_daily_kline(code, count)` | backtest_data 表 → Sina 兜底 | [{day,open,high,low,close,volume}] |
| `get_money_flow(code)` | Sina | 当日资金流向 |
| `get_money_flow_history(code, days)` | Sina | 历史资金流向 |
| `get_fundamental_data(code)` | **MySQL stock_financials 优先** → 东方财富 API 兜底 | 财报+估值 |
| `get_industry_comparison(code)` | 东方财富 | 行业对比 |

### 基本面数据获取（2026-05 变更）

```mermaid
get_fundamental_data(code)
  ├── MySQL stock_financials 表 (优先, <100ms)
  │   ├── EPS/ROE/毛利率/营收/净利润/增速
  │   └── PE = 最新股价 / EPS (自动计算)
  └── 东方财富 push2 API (兜底, HTTPS不可用时走MySQL)
```

基本面批量拉取使用东方财富 DataCenter API：
```
https://datacenter.eastmoney.com/securities/api/data/v1/get
  → reportName: RPT_F10_FINANCE_MAINFINADATA
```

### 数据源特性

| 数据源 | 可用时段 | 限流 |
|--------|----------|------|
| 腾讯 qt.gtimg.cn | 24小时 | 50只/批 + 0.5s间隔 |
| Sina API | 交易时段为主 | HTTP 456 限流 ~2000次 |
| 东方财富 push2 (HTTP) | 24小时 | K线拉取间隔 3-5s/只 |
| 东方财富 DataCenter | 24小时 | 财报拉取间隔 2-4s/只 |
| yfinance (美股) | 24小时 | Too Many Requests 偶发 |
| akshare | 交易时段 | macOS SSL兼容问题(Python 3.9 + LibreSSL) |

> **注意**：macOS 自带 Python 3.9 编译的是 LibreSSL 2.8.3，urllib3 v2 不兼容 HTTPS 请求。东方财富 API 改用 `http://` 协议绕过。

### 腾讯 API 字段索引 (qt.gtimg.cn)

```
parts[3]=price [4]=yclose [33]=high [34]=low [37]=amount(万) [38]=turnover(%) [39]=pe [44]=mc(亿)
```

## technical_indicators.py

计算 MA/EMA/MACD/RSI/KDJ/BOLL/OBV，输出到 `get_comprehensive_data_with_indicators()`。

基本面数据在 comprehensive 接口中**优先获取**（MySQL 毫秒级），前端也通过 `/api/fundamentals/<code>` 独立快速加载。

## 数据拉取脚本

| 脚本 | 用途 |
|------|------|
| `prefetch_backtest_data.py` | 热门板块股票日K线预取 (akshare) |
| `batch_prefetch_all.py` | 全市场数据预取 |
| `pull_financials.py` | 自选股财报拉取 (akshare THS) |
| `pull_financials_extended.py` | 主线股财报批量拉取 |
| `pull_watchlist_financials.py` | 自选股财报 (东方财富 DataCenter API) |
| `fill_missing_data.py` | 逐只补全历史日K线 (东方财富 HTTP) |

## data_formatters.py

将原始数据格式化为 AI prompt 可用的文本格式：`format_for_ai()`, `to_json()`。
