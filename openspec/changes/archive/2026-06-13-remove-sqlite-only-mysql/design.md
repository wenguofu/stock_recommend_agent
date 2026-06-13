# Design — Remove SQLite, MySQL Only

## 1. 引擎工厂重构

### Before (`models.py:30-86`)

```python
def get_database_url():
    env_url = os.environ.get("DATABASE_URL", "")
    if env_url:
        return env_url
    db_path = os.path.join(os.path.dirname(__file__), 'database.db')
    return f'sqlite:///{db_path}'  # ← 兜底

def get_engine(database_url=None):
    url = database_url or get_database_url()
    is_mysql = url.startswith("mysql")
    if is_mysql:
        engine = create_engine(url, pool_size=10, pool_recycle=3600, pool_pre_ping=True)
    else:
        engine = create_engine(url, connect_args={'check_same_thread': False, 'timeout': 15}, ...)
        @event.listens_for(engine, 'connect')
        def _set_sqlite_pragma(dbapi_connection, connection_record):
            cursor.execute('PRAGMA journal_mode=WAL')  # ← SQLite 专用
            ...
```

### After

```python
def get_database_url():
    """获取 MySQL DSN，未设置直接 fail-fast。"""
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL 未设置。\n"
            "本项目仅支持 MySQL，请设置环境变量，例如:\n"
            "  export DATABASE_URL='mysql+pymysql://user:pass@host:3306/stock_trading'"
        )
    if not url.startswith("mysql"):
        raise RuntimeError(
            f"DATABASE_URL 必须是 MySQL DSN (以 mysql:// 开头)，当前: {url[:30]}..."
        )
    return url

def get_engine(database_url=None):
    """创建 MySQL 引擎（唯一支持的 DB 类型）。"""
    url = database_url or get_database_url()
    # 必为 MySQL — get_database_url 已校验
    return create_engine(
        url,
        echo=False,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
```

**删除**：
- `_set_sqlite_pragma` 整个事件监听函数
- `connect_args`（SQLite 专用）
- `from sqlalchemy import event` 导入（如果不再用）
- MySQL 分支判定 `is_mysql`（不再需要，因为已经 fail-fast 在 URL 阶段）

**保留**：
- `reset_engine()`（用于运行时切到不同 MySQL 库，仍是 MySQL-only）
- `from sqlalchemy.dialects.mysql import MEDIUMTEXT`（列定义在用）

### Why fail-fast > 兜底

| 方案 | 启动时未设 DATABASE_URL | 优点 | 缺点 |
|------|------------------------|------|------|
| 兜底 SQLite（当前） | 静默用 SQLite | "能跑就行" | 线上如果 env 漏配，数据写到错的库 |
| **fail-fast（采用）** | 启动报错 | 显式、安全 | 启动时要配 env |

兜底违反"fail loud"原则 — 静默用错库的事故远比"启动报错"难排查。

## 2. 测试 fixture 设计

### 共享 conftest（**扩展**现有 `tests/conftest.py` — 不覆盖）

> ⚠️ `tests/conftest.py` 已存在（pytest 共享 fixtures + 条件跳过），追加而非新建。

```python
# tests/conftest.py (在现有文件末尾追加)
import os
import uuid
import pytest
from sqlalchemy import create_engine, text

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")


def _can_connect_mysql(url: str) -> bool:
    try:
        engine = create_engine(url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def mysql_test_url():
    """MySQL 测试库 URL；不可用时 skip。"""
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL 未设置，跳过需要 MySQL 的测试")
    if not _can_connect_mysql(TEST_DATABASE_URL):
        pytest.skip(f"MySQL 不可达: {TEST_DATABASE_URL[:30]}...")
    return TEST_DATABASE_URL


@pytest.fixture
def mysql_test_schema(mysql_test_url):
    """建临时 schema, yield engine, teardown 删 schema。
    schema 名用 uuid4 后缀避免并行 CI 时撞名。
    """
    from models import Base
    schema_name = f"stock_test_{os.getpid()}_{uuid.uuid4().hex[:8]}"
    base_url = mysql_test_url.rsplit("/", 1)[0]
    engine = create_engine(
        f"{base_url}/{schema_name}?charset=utf8mb4",
        pool_pre_ping=True,
    )
    with engine.begin() as conn:
        conn.execute(text(f"CREATE DATABASE `{schema_name}` CHARACTER SET utf8mb4"))
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        try:
            with engine.begin() as conn:
                conn.execute(text(f"DROP DATABASE IF EXISTS `{schema_name}`"))
        finally:
            engine.dispose()
```

### test_db.py fixture 改造

```python
@pytest.fixture
def db_session(mysql_test_schema, monkeypatch):
    """MySQL 测试 schema + 替换 models.engine/SessionLocal, teardown 还原"""
    import models
    orig_engine = models.engine
    orig_session = models.SessionLocal
    TestSession = sessionmaker(bind=mysql_test_schema)
    monkeypatch.setattr(models, "engine", mysql_test_schema)
    monkeypatch.setattr(models, "SessionLocal", TestSession)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        # monkeypatch 会在 fixture 退出时自动还原, 这里保险起见显式再赋一次
        models.engine = orig_engine
        models.SessionLocal = orig_session
```

### test_zisuye.py fixture 改造

```python
@pytest.fixture(scope="function")
def test_db(mysql_test_schema, monkeypatch):
    """MySQL 测试 schema + 替换全局 SessionLocal, teardown 还原"""
    import models
    orig_engine = models.engine
    orig_session = models.SessionLocal
    orig_zisuye_session = zisuye.SessionLocal
    TestSession = sessionmaker(bind=mysql_test_schema)
    monkeypatch.setattr(models, "engine", mysql_test_schema)
    monkeypatch.setattr(models, "SessionLocal", TestSession)
    monkeypatch.setattr(zisuye, "SessionLocal", TestSession)
    try:
        yield TestSession
    finally:
        models.engine = orig_engine
        models.SessionLocal = orig_session
        zisuye.SessionLocal = orig_zisuye_session
```

**设计要点**：
- 不可达时 `pytest.skip` 而非 fail — 保留 CI 灵活性
- 用临时 schema 隔离测试数据，避免污染 dev 库
- 同一 `TEST_DATABASE_URL` 派生临时库名 `stock_test_<pid>_<objid>` 防并发冲突

## 3. pipeline/train.py 改造

### Before

```python
# pipeline/train.py:51-69
import sqlite3
db_path = os.path.join(PROJECT_ROOT, "database.db")
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    df = pd.read_sql("SELECT ... FROM backtest_data WHERE date >= ?", conn)
    conn.close()
```

### After

```python
# pipeline/train.py
from models import SessionLocal, BacktestData

def load_training_data(time_window: str = "2y") -> pd.DataFrame:
    days = {"1y": 365, "2y": 730, "3y": 1095}.get(time_window, 730)
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    logger.info(f"Loading training data from MySQL, window={time_window}")

    session = SessionLocal()
    try:
        stmt = (
            select(BacktestData.code, BacktestData.date,
                   BacktestData.open, BacktestData.high, BacktestData.low,
                   BacktestData.close, BacktestData.volume)
            .where(BacktestData.date >= cutoff)
            .order_by(BacktestData.code, BacktestData.date)
        )
        # SQLAlchemy 2.0 idiom: 用 session.get_bind() 而非 session.bind (deprecated)
        df = pd.read_sql(stmt, session.get_bind())
    finally:
        session.close()

    if len(df) > 0:
        return df

    # 兜底: 合成数据 (保留 — 之前就有, 不依赖 DB 类型)
    return _synthetic_data()
```

**关键点**：`pd.read_sql(stmt, session.bind)` — `stmt` 是 SQLAlchemy `Select` 对象，`bind` 是 MySQL engine。比手拼 SQL 安全（防注入），且与列类型同步。

## 4. 文档同步清单

| 文件 | 改动 |
|------|------|
| `README.md:53` | 删 "DATABASE_URL 默认指向 MySQL，如需切回 SQLite 注释掉即可" → 改 "DATABASE_URL 必填 (MySQL DSN)" |
| `README.md:64` | env 表里 `DATABASE_URL` 描述从 "支持 SQLite/MySQL" → "必填 (MySQL DSN)" |
| `README.md:81` | 删 "26表, 支持 SQLite/MySQL" → "26表 (MySQL)" |
| `README.md:93` | 删 "SQLite→MySQL 迁移脚本" 描述（脚本已删） |
| `README.md:218` | archive 列表保留 `2026-05-30-sqlite-to-mysql` 条目（历史记录） |
| `docs/paper-trading-plan.md:12` | "SQLite + Base.metadata.create_all" → "MySQL DDL 自动同步（Base.metadata.create_all）" |
| `openspec/specs/core.md:11/32/37/60/65` | 见 Spec 变更章节 |

## 5. 实施顺序

1. 写 `tests/test_engine_factory.py`（4 个新测试）— 确认 RED
2. 改 `models.py` + `config.py` — 确认 GREEN
3. 改 `tests/conftest.py` 新建 + `test_db.py` + `test_zisuye.py` — 改用 MySQL fixture
4. 改 `pipeline/train.py` — 改用 SessionLocal
5. 删 `migrate_to_mysql.py` + 删 `database.db*` / `stock_*.db` / `scripts/database.db`
6. 改 `.env` / `.env.example` / `docker-compose.yml`
7. 改 `README.md` / `docs/paper-trading-plan.md` / `openspec/specs/core.md`
8. 全量 `pytest -q tests/` + `openspec validate --strict`
9. 归档 OpenSpec change
