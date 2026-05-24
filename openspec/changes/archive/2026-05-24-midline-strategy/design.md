## Why

现有系统面向机构量化（3400只扫描、21因子、11Agent辩论），对小资金散户中线交易过度复杂。

## What Changes

### 策略导航
- `Layout.tsx`: 新增顶部策略切换栏 `⚡ 短线量化 | 📊 中长线交易`
- 短线量化模式显示原有全部导航项
- 中长线模式显示 4 项精简导航

### 后端 API (`midline_routes.py`)
- `GET /api/midline/watchlist-health` — 自选池趋势健康度（MA排列+MACD+RSI 三信号评分 0-100）
- `GET /api/midline/signals/<code>` — 单只股票信号灯详情
- `POST /api/midline/position-calc` — 仓位计算器（输入资金/风险%/入场/止损 → 输出股数/盈亏比）
- `GET/POST /api/midline/journal` — 交易日志 CRUD
- `PUT/DELETE /api/midline/journal/<id>`
- `GET /api/midline/journal/stats` — 交易统计（胜率/盈亏比/连胜连败）

### 数据库
- `models.py`: 新增 `trade_journal` 表（17字段）

### 前端页面
- `Midline.tsx`: 中长线看板，四面板：
  1. 自选池趋势健康度表格（评分/均线/MACD/RSI/趋势/建议）
  2. 仓位计算器（输入→计算→显示建议股数+盈亏比）
  3. 交易统计（胜率/盈亏比/累计/连胜/连败/均盈/均亏）
  4. 交易日志（列表+快捷记录+删除）

## Impact

- 纯增量，不影响现有量化功能
- 中长线 API 使用独立路由文件
