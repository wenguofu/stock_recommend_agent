"""
pytest 配置 — 共享 fixtures 和条件跳过
"""
import os
import sys
import uuid
import pytest
from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 标记：需要完整依赖的测试
requires_flask = pytest.mark.skipif(
    not __import__("importlib").util.find_spec("flask"),
    reason="flask 未安装",
)

# ── MySQL 测试库 (Sprint: 移除 SQLite) ──

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
    """MySQL 测试库 URL；不可用时 skip。

    设置方式: export TEST_DATABASE_URL='mysql+pymysql://user:pass@host:3306/'
    """
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL 未设置，跳过需要 MySQL 的测试")
    if not _can_connect_mysql(TEST_DATABASE_URL):
        pytest.skip(f"MySQL 不可达: {TEST_DATABASE_URL[:40]}...")
    return TEST_DATABASE_URL


@pytest.fixture
def mysql_test_schema(mysql_test_url):
    """建临时 schema, yield engine, teardown 删 schema。

    schema 名用 uuid4 后缀避免并行 CI 撞名。
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
