# Fetch A-Share Fundamentals

Pull fundamental financial data for A-share stocks from East Money DataCenter API and store in MySQL `stock_financials` table.

## Quick Usage

When the user asks to pull/migrate/fetch fundamental data, run:

```bash
cd /Users/wgfu/work/a-stock-trading && python3 scripts/fetch_fundamentals.py <args>
```

## Common patterns

| User request | Command |
|---|---|
| "拉取600487的基本面" | `--code 600487` |
| "拉取自选股的基本面" | `--watchlist` |
| "强制刷新自选股基本面" | `--watchlist --force` |
| "检查哪些自选股需要更新" | `--watchlist --dry-run` |
| "拉取600487和000001的基本面" | `--codes 600487,000001` |
| "从文件拉取基本面" | `--file stocks.txt` |

## Options

```
--code CODE       Single stock code
--codes A,B,C     Multiple codes (comma separated)
--watchlist       All non-US watchlist stocks
--file PATH       Read codes from file (one per line)
--force           Force refresh (ignore existing data)
--dry-run         Check only, don't pull
--delay N         Seconds between requests (default 3)
--include-688     Include 科创板 stocks
```

## Data Source

- **API**: East Money `RPT_F10_FINANCE_MAINFINADATA` (165 fields)
- **URL**: `https://datacenter.eastmoney.com/securities/api/data/v1/get`
- **Rate limit**: 2-4s between requests to avoid throttling

## Fields stored

EPS, ROE, gross_margin, revenue, net_profit, revenue_yoy, profit_yoy, total_assets, report_date, report_type

## Important

- macOS Python 3.9 + LibreSSL: use `verify=False`, API calls have retry logic
- Only stores 年报 (12-31) and 一季报 (03-31) for efficiency
- Data goes to MySQL `stock_trading.stock_financials` table
- Fundamental display: `/api/fundamentals/<code>` (MySQL, <100ms)
