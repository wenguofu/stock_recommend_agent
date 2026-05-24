# Core — API 服务与配置

## api_server.py

Flask 应用入口，CORS 全开，集成请求日志中间件。

| 配置项 | 环境变量 | 默认值 |
|--------|----------|--------|
| 端口 | `API_PORT` | 35000 |
| Debug | `FLASK_DEBUG=1` | `False` |
| 数据库 | 硬编码 `database.db` | — |

### 路由注册

```python
register_routes(app)       # api_routes.py (主路由，3898行)
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
```

### 消费者

- `scheduler.py` — 使用 `f"{API_BASE}/api/..."`
- `sector_analysis.py`, `scripts/recommendation_gen.py`, `scripts/sector_update.py`, `sector_utils.py`
- 前端通过 `import.meta.env.VITE_API_BASE_URL` + `.env` 覆盖

## models.py

SQLAlchemy ORM，21 张表，SQLite。

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

## db.py

CRUD 操作层，1012 行。`search_etf_replacement()` 内嵌 688xxx→588000 兜底逻辑。

### 已知问题

- [ ] `DB_PATH` 硬编码，不支持环境变量覆盖
- [ ] `search_etf_replacement()` 返回 dict 而非 ORM 对象（类型不一致）
- [ ] `create_paper_account()` 有死代码 `if "auto_trade" in kwargs`（kwargs 已在签名中显式声明）
