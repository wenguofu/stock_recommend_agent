# Core — API 服务与配置

## api_server.py

Flask 应用入口，CORS 全开，集成请求日志中间件。

| 配置项 | 环境变量 | 默认值 |
|--------|----------|--------|
| 端口 | `API_PORT` | 35000 |
| Debug | `FLASK_DEBUG=1` | `False` |
| 数据库 | `DATABASE_URL` | `sqlite:///database.db` |

### 路由注册

```python
register_routes(app)       # api_routes.py (主路由)
register_risk_routes(app)  # risk_routes.py (风险管理)
register_factor_routes(app)# factor_routes.py (因子+ML)
```

### 调度器

`start_scheduler()` 在 `__name__ == '__main__'` 时启动内置 TaskScheduler，替代 Hermes cron。

## config.py

共享配置模块，所有脚本统一入口：

```python
API_BASE = os.environ.get("A_STOCK_API", "http://127.0.0.1:35000")
API_PORT = int(os.environ.get("API_PORT", 35000))
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///database.db")
```

## models.py

SQLAlchemy ORM，26 张表。**支持 SQLite / MySQL 双引擎**，通过 `DATABASE_URL` 环境变量切换。

| 表 | 用途 |
|----|------|
| watchlist | 自选股+持仓 |
| config | 键值配置 |
| agents | AI Agent 定义 |
| debate_jobs | 辩论任务 |
| kline_cache | K线缓存 |
| paper_* | 模拟盘(账户/持仓/订单/快照/计划/规则) |
| backtest_* | 回测缓存 |
| stock_financials | 基本面 |
| risk_reports | 风险缓存 |
| recommendations | 推荐结果 |
| recommendation_tracks | 推荐跟踪 |
| trade_journal | 交易日志 |
| market_alert_log | 大盘预警 |
| portfolio_configs | 组合配置 |
| monitor_tasks | 盯盘任务 |

### 引擎工厂

```python
get_engine(url=None)  # 根据 DATABASE_URL 创建引擎
reset_engine(url)     # 运行时切换数据库
```

- MySQL: pool_size=10, pool_recycle=3600, pool_pre_ping=True
- SQLite: WAL 模式, check_same_thread=False, busy_timeout=15s
- `.env` 文件自动加载（通过 python-dotenv）

## db.py

CRUD 操作层，1012 行。包含自选股、Agent、策略、辩论任务、模拟盘、ETF映射、推荐、财务数据、K线缓存、回测数据的完整 CRUD。
