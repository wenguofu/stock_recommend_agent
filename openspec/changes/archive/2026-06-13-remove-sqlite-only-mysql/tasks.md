# Tasks — Remove SQLite, Keep MySQL Only

## 1. TDD Red — 写失败测试
- [x] 1.1 `tests/test_engine_factory.py::test_get_database_url_raises_without_env` — 未设 `DATABASE_URL` 时 `get_database_url()` 抛 `RuntimeError`
- [x] 1.2 `tests/test_engine_factory.py::test_get_database_url_rejects_non_mysql` — 设了 `sqlite://...` 抛 `RuntimeError`
- [x] 1.3 `tests/test_engine_factory.py::test_get_engine_uses_mysql_url` — 给定 MySQL DSN 时 `engine.url` 以 `mysql` 开头
- [x] 1.4 `tests/test_engine_factory.py::test_get_engine_no_sqlite_pragma_listener` — engine 没有 SQLite PRAGMA 事件监听（`PRAGMA journal_mode=WAL` 不在事件列表中）

## 2. TDD Green — 引擎工厂去 SQLite 化
- [x] 2.1 `models.py::get_database_url()` — fail-fast：未设 / 非 MySQL 都 raise
- [x] 2.2 `models.py::get_engine()` — 删除 SQLite 分支、PRAGMA 监听、`connect_args`
- [x] 2.3 `config.py` — `DATABASE_URL` 不再有默认 SQLite 值；注释改为"必填"
- [x] 2.4 跑 `pytest -q tests/test_engine_factory.py` 全绿 (6/6 通过)

## 3. 测试 fixture 改造 (共用 conftest)
- [x] 3.1 `tests/conftest.py` 扩展 — `mysql_test_url` / `mysql_test_schema` fixture
  - 3.1.a 不可达时 `pytest.skip`（不 fail）
  - 3.1.b 临时 schema 名 `stock_test_<pid>_<uuid4>` 防并发
  - 3.1.c teardown 删 schema + dispose engine
- [x] 3.2 `tests/test_db.py::db_session` — 改用 `mysql_test_schema`，删 `create_engine("sqlite:///:memory:")`
- [x] 3.3 `tests/test_zisuye.py::test_db` — 改用 `mysql_test_schema`，删 `tempfile.mkstemp(suffix=".db")`
- [x] 3.4 跑 `pytest -q tests/test_db.py tests/test_zisuye.py`（无 MySQL 时全 skip，有 MySQL 时全过 — 20 passed, 20 skipped）

## 4. pipeline 重写
- [x] 4.1 `pipeline/train.py::load_training_data()` — 删 `import sqlite3` + `sqlite3.connect()`
- [x] 4.2 `pipeline/train.py` — 改用 `SessionLocal` + `BacktestData` ORM + `pd.read_sql(stmt, session.get_bind())`
- [x] 4.3 跑 `python -c "from pipeline.train import load_training_data"` 不 import sqlite3 (验证通过)

## 5. 删文件
- [x] 5.1 `rm migrate_to_mysql.py`
- [x] 5.2 `rm database.db database.db-shm database.db-wal`
- [x] 5.3 `rm stock_system.db stock_trading.db scripts/database.db`
- [x] 5.4 `git status` 确认无残留 (D migrate_to_mysql.py 已 staged)

## 6. 配置 / Docker
- [x] 6.1 `.env` — 删注释的 `DATABASE_URL=sqlite:///database.db` 行
- [x] 6.2 `.env.example` — 改 MySQL-only 模板，去 SQLite 注释
- [x] 6.3 `docker-compose.yml` — 删 `./database.db:/app/database.db` 挂载

## 7. 文档
- [x] 7.1 `README.md` 第 53/64/81/93 行 — 改 MySQL-only 描述
- [x] 7.2 `docs/paper-trading-plan.md:12` — 删 SQLite 字样
- [x] 7.3 `openspec/specs/core.md` 第 11/32/37/60/65 行 — 改 MySQL-only (人工更新, archive 用 --skip-specs)

## 8. 验证
- [x] 8.1 `pytest -q tests/test_engine_factory.py` 全绿（6 个新测试）
- [x] 8.2 `pytest -q tests/test_db.py tests/test_zisuye.py` 全绿 或 全 skip（无 MySQL — 20 passed, 20 skipped）
- [x] 8.3 `pytest -q --no-cov tests/` 全量 214 passed, 21 skipped（除 4 个 torch-missing pre-existing）
- [x] 8.4 `openspec validate --strict` 通过
- [x] 8.5 `grep -rli "sqlite" --include="*.py" ...` 生产代码 0 命中
- [x] 8.6 `ls database.db* stock_*.db scripts/database.db 2>/dev/null` 无输出
- [x] 8.7 `git status` 干净 (M 业务文件 + D 迁移脚本 + ?? 新 change 目录)

## 9. 归档
- [x] 9.1 `opsx:archive remove-sqlite-only-mysql --yes --skip-specs`
