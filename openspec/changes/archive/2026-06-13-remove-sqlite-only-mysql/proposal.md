# Remove SQLite — Keep MySQL Only

## Why

项目已经从 SQLite 迁到 MySQL 三个月（archive `2026-05-30-sqlite-to-mysql/`），但生产代码里仍保留 SQLite 双引擎支持：每次启动要走 `url.startswith("mysql")` 分支判断，引擎工厂要装 PRAGMA 事件监听，`config.py` 默认值还是 `sqlite:///database.db`，`pipeline/train.py` 还在用 `sqlite3` 直连 `database.db`。这些遗留让"我们用 MySQL"这件事需要靠环境变量才成立，违背配置显式原则。

**目标：MySQL MUST 是唯一支持的 DB 引擎；缺少 `DATABASE_URL` MUST 在启动时直接报错，而不是悄悄回落到 SQLite。**

## What Changes

### 1. 引擎工厂去 SQLite 化
- `models.py::get_database_url()` — 删除 SQLite 默认 URL，**没有 `DATABASE_URL` 直接 raise `RuntimeError`**（启动时 fail-fast）
- `models.py::get_engine()` — 删除 `else` 分支（PRAGMA / `check_same_thread` / `connect_args`），保留 MySQL 配置（pool_size=10 / pool_recycle=3600 / pool_pre_ping）
- `models.py::reset_engine()` — 保留（用于运行时切换到别的 MySQL 库，仍是 MySQL-only）

### 2. 配置清理
- `config.py` — `DATABASE_URL` 不再有 SQLite 默认值；注释说明改为"必须设置"
- `.env` — 删除被注释的 `DATABASE_URL=sqlite:///database.db` 提示行
- `.env.example` — 只留 MySQL 模板（带 `change-me` 占位密码）
- `docker-compose.yml` — 删除 `./database.db:/app/database.db` 挂载

### 3. 移除迁移脚本
- 删除 `migrate_to_mysql.py`（一次性脚本，已归档过）
- archive `openspec/changes/archive/2026-05-30-sqlite-to-mysql/` 整目录保留为历史记录（设计文档 `design.md`）

### 4. pipeline 重写
- `pipeline/train.py::load_training_data()` — 移除 `import sqlite3` + `sqlite3.connect("database.db")`，改用 `models.SessionLocal` + `models.BacktestData` ORM 查 `backtest_data` 表（MySQL）

### 5. 测试 fixture 改造
- `tests/test_db.py::db_session` — 不再 `create_engine("sqlite:///:memory:")`，改用 `TEST_DATABASE_URL` 环境变量指向的 MySQL 测试库（`stock_trading_test`），fixture 建临时 schema、灌 `Base.metadata.create_all`、teardown 删 schema
- `tests/test_zisuye.py::test_db` — 同上：MySQL 测试库 + 临时 schema
- `tests/test_valuation_forecast.py` 注释 — 更新文案（`prediction_aggregates` 不存在是 ORM 创建时序问题，与 DB 引擎无关）
- `tests/test_e2e_integration.py` 注释 — 更新为"需要 MySQL 测试库"

### 6. 删 SQLite 数据文件
- `database.db` / `database.db-shm` / `database.db-wal`
- `stock_system.db` / `stock_trading.db`（零字节空文件，无任何代码引用）
- `scripts/database.db`（零字节空文件）

### 7. 文档同步
- `README.md` 第 53/64/81/93/218 行 — 删除 SQLite 描述
- `docs/paper-trading-plan.md:12` — 删除"SQLite + Base.metadata.create_all 自动重建"
- `openspec/specs/core.md` — 改 SQLite/MySQL 双引擎描述为 MySQL-only

## Out of Scope

- 不动 26 张 ORM 表的 schema（既已迁到 MySQL，列类型/索引沿用现状）
- 不动 MySQL 连接池调参（pool_size / pool_recycle / pool_pre_ping 沿用）
- 不改 `MEDIUMTEXT` 等 MySQL-specific 列定义
- 不写"自动迁移到其它 DB"适配层
- 不动 `.gitignore` 里 `*.sqlite` / `*.sqlite3` 兜底规则（防御性保留）

## Spec 变更

`openspec/specs/core.md` 第 11/32/37/60/65 行 — 改写为 MySQL-only：
- 默认值改为"`DATABASE_URL` 必须设置（MySQL DSN）"
- 删除"支持 SQLite / MySQL 双引擎"描述
- 引擎工厂章节删除 SQLite 分支描述

## 验收

1. **fail-fast 行为**：`DATABASE_URL` 未设时 `python -c "import models"` 抛 `RuntimeError`，不再回落 SQLite
2. **引擎特征**：`models.engine.url` 以 `mysql` 开头；engine 没有 SQLite PRAGMA 事件监听（通过 `event.contains()` 验证）
3. **pipeline 改造**：`python -c "from pipeline.train import load_training_data"` 不再 import `sqlite3`
4. **测试可跑**：`pytest -q tests/test_engine_factory.py` 全绿（≥ 4 个新测试覆盖 fail-fast / 引擎特征）
5. **测试仍通过**：`pytest -q tests/test_db.py tests/test_zisuye.py` 在 MySQL 测试库可连通时全绿；不可连通时 `pytest.skip`
6. **openspec 严格通过**：`openspec validate --strict` 无 error
7. **git 干净**：`git status` 无 SQLite 残留（`database.db*` / `stock_*.db` / `scripts/database.db` 已删）

## 风险

- **MySQL 测试库依赖**：test_db.py / test_zisuye.py 改用 MySQL 后，本地无 MySQL 时 fixture 必须能 skip（用 `pytest.importorskip` 或环境变量探测），不能直接把 dev 环境搞挂
- **生产环境 DATABASE_URL**：用户已设 MySQL URL（`.env:4`），但若部署脚本里有人依赖 SQLite 默认值会启动失败 — 文档必须明示
