# core delta — Remove SQLite, MySQL Only

## MODIFIED Requirements

### Requirement: DATABASE_URL 必须为 MySQL DSN

`models.get_database_url()` **MUST** 返回 MySQL DSN（`mysql+pymysql://...`）；未设置环境变量或 URL 不以 `mysql` 开头时，**MUST** 抛出 `RuntimeError`（fail-fast）。

#### Scenario: 未设置 DATABASE_URL

- **WHEN** 进程启动时 `os.environ.get("DATABASE_URL", "")` 返回空串
- **THEN** `get_database_url()` **MUST** raise `RuntimeError`，错误信息提示用户设置 `export DATABASE_URL='mysql+pymysql://...'`
- **AND** 进程不创建任何 engine，导入即崩

#### Scenario: 设置了 SQLite URL

- **WHEN** `DATABASE_URL=sqlite:///database.db` 或任何不以 `mysql` 开头的 URL
- **THEN** `get_database_url()` **MUST** raise `RuntimeError`，错误信息明示"必须为 MySQL DSN"
- **AND** 不再静默回落到 SQLite

#### Scenario: 设置了合法 MySQL DSN

- **WHEN** `DATABASE_URL=mysql+pymysql://user:pass@host:3306/stock_trading`
- **THEN** `get_database_url()` **MUST** 返回该 URL 原样
- **AND** `get_engine()` **MUST** 用 MySQL 配置创建 engine（pool_size=10, pool_recycle=3600, pool_pre_ping=True）

### Requirement: 引擎工厂不再有 SQLite 分支

`models.get_engine()` **MUST** 仅产出 MySQL 引擎；不再注册 SQLite PRAGMA 事件监听、不再设置 `check_same_thread=False`。

#### Scenario: engine URL 前缀

- **WHEN** 给定合法 MySQL DSN
- **THEN** `engine.url` 的 `drivername` **MUST** 以 `mysql` 开头

#### Scenario: 无 SQLite 事件监听

- **WHEN** 创建 engine 后
- **THEN** engine **MUST NOT** 监听 `'connect'` 事件执行 `PRAGMA journal_mode=WAL` 等 SQLite 专用语句
- **AND** engine **MUST NOT** 设置 `connect_args={'check_same_thread': False}`

#### Scenario: reset_engine 仍可用 (跨 MySQL 库运行时切换)

- **WHEN** 调用 `reset_engine("mysql+pymysql://other:3306/other_db")`
- **THEN** 全局 `engine` / `SessionLocal` 绑定到新 MySQL DSN
- **AND** 不再支持切到非 MySQL

### Requirement: config.py 不再兜底 SQLite

`config.DATABASE_URL` **MUST** 直接读 `os.environ.get("DATABASE_URL")`，无默认 SQLite 字符串；缺值返回 `""` 由 `models.get_database_url()` 负责 fail-fast。

#### Scenario: 缺 DATABASE_URL 时 config 返回空串

- **WHEN** 环境变量无 `DATABASE_URL`
- **THEN** `config.DATABASE_URL` **MUST** 等于 `""`（不兜底 `sqlite:///database.db`）
- **AND** `models.get_database_url()` 在此基础上 raise `RuntimeError`

## REMOVED Requirements

### Requirement: SQLite 双引擎支持 (已删除)

原 spec 中"支持 SQLite / MySQL 双引擎"章节整段移除：

- `get_database_url()` 的 `sqlite:///database.db` 兜底
- `get_engine()` 的 SQLite `else` 分支（含 `check_same_thread` / WAL / busy_timeout 配置）
- `migrate_to_mysql.py` 一次性迁移脚本（归档于 `openspec/changes/archive/2026-05-30-sqlite-to-mysql/`）

#### Scenario: 项目根目录不再有 SQLite 数据文件

- **WHEN** 完成本变更的代码 + 文档同步
- **THEN** `database.db` / `database.db-shm` / `database.db-wal` **MUST NOT** 存在
- **AND** `stock_system.db` / `stock_trading.db` / `scripts/database.db` **MUST NOT** 存在
- **AND** `git status` 报告这些文件被删除

#### Scenario: 生产代码不再 import sqlite3 / 引用 sqlite://

- **WHEN** 跑 `grep -rE "sqlite3|sqlite://" --include="*.py" .`（排除 `openspec/changes/archive/2026-05-30-sqlite-to-mysql/`）
- **THEN** **MUST** 无任何生产代码命中
- **AND** `import sqlite3` **MUST NOT** 出现在 `pipeline/train.py` 等业务脚本
