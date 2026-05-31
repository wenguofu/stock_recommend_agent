# SQLite → MySQL 数据存储迁移

**日期**: 2026-05-30
**状态**: 已完成

## 动机

- SQLite 171MB 单文件，WAL 模式下并发瓶颈
- 缺少连接池、字符集、原生并发支持
- macOS Python 3.9 的 LibreSSL 导致 HTTPS API 不可用

## 变更内容

### Phase 1: 基础设施
- `models.py`: `get_engine()` 工厂函数，`DATABASE_URL` 环境变量切换引擎
- `config.py`: 新增 `DATABASE_URL` 配置
- `requirements.txt`: 新增 `pymysql`, `cryptography`, `python-dotenv`
- 补全 `RecommendationTrack` 模型（修复 `recommendation_tracker.py` 重复定义）

### Phase 2: 数据迁移
- `migrate_to_mysql.py`: SQLite → MySQL 全量迁移脚本
- 26 张表，1,274,689 行数据，行数一致验证通过
- 修复 `debate_jobs.code` String(6) → String(500)（多股辩论存逗号列表）
- 修复 `debate_jobs.steps/report_md` Text → MEDIUMTEXT（数据超 64KB）

### Phase 3: 读取层切换
- 9 个文件从 `sqlite3.connect()` 改为 `SessionLocal` + SQLAlchemy
- SQL 兼容修复: `GLOB→REGEXP`, `RANDOM()→RAND()`, `func.date()→datetime`
- 基本面数据源: 东方财富 HTTPS API → MySQL `stock_financials` 表优先
- 前端基本面独立加载: `/api/fundamentals/<code>` 76ms (原 15s)

### Phase 4: 数据补齐
- `fill_missing_data.py`: 东方财富 HTTP API 补全日K线
- `pull_watchlist_financials.py`: 东方财富 DataCenter API 补全财报
- 自选股 38/38 覆盖基本面和日K线

## 涉及文件 (21个)

```
models.py, config.py, db.py, requirements.txt, .env, .env.example
api_routes.py, data_fetchers.py, technical_indicators.py
tune_rf_fast.py, tune_rf_v3.py, tune_random_forest.py
validate_ml_risk.py, backtest_timing_pf.py, db_scanner.py
strategies/breakout.py, strategies/tenbagger.py
scripts/refresh_watchlist.py
stock_frontend/src/pages/StockDetail.tsx
stock_frontend/src/services/api.ts
```

## 新增文件

```
migrate_to_mysql.py          # 迁移脚本
fill_missing_data.py          # 日K补全
pull_watchlist_financials.py  # 财报补全
.env                          # MySQL 连接配置
```
