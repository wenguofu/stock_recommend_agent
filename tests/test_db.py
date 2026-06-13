"""
测试 ORM 模型 — models.py + db.py
"""
import os
import sys
import pytest
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 需要 sqlalchemy；不可用时整个模块跳过
try:
    from sqlalchemy import create_engine
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False

pytestmark = pytest.mark.skipif(not HAS_SQLALCHEMY, reason="sqlalchemy 未安装")


@pytest.fixture
def db_session(mysql_test_schema, monkeypatch):
    """MySQL 测试 schema + 替换 models.engine/SessionLocal, teardown 还原。"""
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
        models.engine = orig_engine
        models.SessionLocal = orig_session


class TestWatchlist:
    def test_add_watchlist(self, db_session):
        from db import add_to_watchlist
        item = add_to_watchlist(db_session, "300679", "电连技术", cost_price=55.51, shares=200)
        assert item.code == "300679"
        assert item.name == "电连技术"
        assert item.cost_price == 55.51
        assert item.shares == 200

    def test_update_existing(self, db_session):
        from db import add_to_watchlist
        add_to_watchlist(db_session, "000001", "平安银行", cost_price=10.0)
        item = add_to_watchlist(db_session, "000001", "平安银行", cost_price=12.0, shares=500)
        assert item.cost_price == 12.0
        assert item.shares == 500

    def test_remove_watchlist(self, db_session):
        from db import add_to_watchlist, remove_from_watchlist
        add_to_watchlist(db_session, "000001", "平安银行")
        assert remove_from_watchlist(db_session, "000001") is True
        assert remove_from_watchlist(db_session, "999999") is False


class TestConfig:
    def test_set_and_get(self, db_session):
        from db import set_config, get_config
        set_config(db_session, "test_key", "test_value")
        assert get_config(db_session, "test_key") == "test_value"

    def test_get_default(self, db_session):
        from db import get_config
        assert get_config(db_session, "no_such_key", "fallback") == "fallback"


class TestModels:
    def test_all_tables_created(self):
        from models import Base
        tables = Base.metadata.tables.keys()
        required = ["watchlist", "config", "agents", "debate_jobs",
                     "paper_accounts", "paper_positions", "paper_orders",
                     "kline_cache", "stock_financials", "risk_reports"]
        for t in required:
            assert t in tables, f"表 {t} 不存在"

    def test_watchlist_fields(self):
        from models import Watchlist
        assert hasattr(Watchlist, "code")
        assert hasattr(Watchlist, "cost_price")
        assert hasattr(Watchlist, "shares")
