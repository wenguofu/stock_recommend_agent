"""
测试 models.py 的引擎工厂去 SQLite 化行为。

设计:
  - `models.py` 模块底部 `Base.metadata.create_all(engine)` 和 `ensure_schema()`
    会真连 MySQL 查表 — 用 `mock.patch("sqlalchemy.create_engine")` 切断
  - `models.py:18-22` import 时自动 `load_dotenv(.env)` — mock 掉
  - 每个测试通过 helper `_load_models(env_url)` 控制:
      1) 设 DATABASE_URL = env_url (让 reload 成功)
      2) 启动 mock.patch 上下文
      3) `importlib.reload(models)` 重新执行模块级代码
      4) 返回 (models, mock_create) 给测试体

验证:
  1. 未设 DATABASE_URL → 启动 fail-fast (RuntimeError)
  2. 设了 SQLite URL → 拒绝, 提示必须 MySQL
  3. 设了 MySQL URL → 原样返回
  4. create_engine 收到 MySQL DSN
  5. event.listens_for 不再注册 PRAGMA 函数
  6. create_engine 不再传 check_same_thread connect_args
"""
import importlib
import os
import sys
from unittest import mock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


MOCK_MYSQL_URL = "mysql+pymysql://mocksql:mock@127.0.0.1:3306/mock_db"


def _make_mock_engine(url: str) -> mock.MagicMock:
    eng = mock.MagicMock()
    eng.url.drivername = url.split("://", 1)[0]
    return eng


class _ModelsLoader:
    """上下文管理器: setenv DATABASE_URL + mock dotenv/create_engine + reload models。

    用法:
        with _ModelsLoader() as ctx:
            ctx.models.get_database_url()
            ctx.mock_create.call_args  # 检查 create_engine 的入参
    """
    def __init__(self, initial_url: str = MOCK_MYSQL_URL):
        self.initial_url = initial_url
        self.mock_create = None
        self.models = None

    def __enter__(self):
        # mock create_engine
        self._create_patch = mock.patch("sqlalchemy.create_engine")
        mock_create = self._create_patch.__enter__()
        mock_create.side_effect = lambda url, **kw: _make_mock_engine(url)
        self.mock_create = mock_create

        # mock dotenv
        self._dotenv_patch = mock.patch("dotenv.load_dotenv", return_value=None)
        self._dotenv_patch.__enter__()

        # 设 DATABASE_URL
        if self.initial_url is not None:
            os.environ["DATABASE_URL"] = self.initial_url
        else:
            os.environ.pop("DATABASE_URL", None)

        # 记下 reload 之前的 engine / SessionLocal, 退出时还原
        # (避免 mock 引擎污染到后续依赖真实 engine 的测试)
        import models
        self._orig_engine = models.engine
        self._orig_session = models.SessionLocal
        importlib.reload(models)
        self.models = models
        return self

    def __exit__(self, *args):
        # 先还原全局 engine, 再退出 mock 上下文
        try:
            if hasattr(self, "_orig_engine") and self._orig_engine is not None:
                self.models.engine = self._orig_engine
                self.models.SessionLocal = self._orig_session
        except Exception:
            pass
        self._dotenv_patch.__exit__(*args)
        self._create_patch.__exit__(*args)
        os.environ.pop("DATABASE_URL", None)


@pytest.fixture
def loader():
    """默认 loader: 用 mock MySQL URL 装载 models。"""
    with _ModelsLoader() as ctx:
        yield ctx


class TestGetDatabaseUrl:
    def test_missing_database_url_raises_runtime_error(self, loader):
        """测试运行时清掉 DATABASE_URL, 调用函数必须 raise。"""
        os.environ.pop("DATABASE_URL", None)
        with pytest.raises(RuntimeError, match="DATABASE_URL"):
            loader.models.get_database_url()

    def test_sqlite_url_rejected(self, loader):
        """运行时设 SQLite URL, 必须 raise。"""
        os.environ["DATABASE_URL"] = "sqlite:///database.db"
        with pytest.raises(RuntimeError, match="MySQL"):
            loader.models.get_database_url()

    def test_mysql_url_accepted(self, loader):
        """运行时设 MySQL URL, 必须原样返回。"""
        url = "mysql+pymysql://user:pass@127.0.0.1:3306/stock_trading"
        os.environ["DATABASE_URL"] = url
        assert loader.models.get_database_url() == url


class TestGetEngine:
    def test_create_engine_receives_mysql_url(self, loader):
        """get_engine() 调 create_engine 时, URL 以 mysql 开头。"""
        loader.models.get_engine()
        assert loader.mock_create.called, "create_engine 未被调用"
        call_args = loader.mock_create.call_args
        actual_url = call_args[0][0]
        assert actual_url.startswith("mysql"), (
            f"create_engine 收到非 MySQL URL: {actual_url!r}"
        )

    def test_no_sqlite_pragma_event_listener(self, loader):
        """get_engine() 不再注册 SQLite PRAGMA 事件监听。"""
        with mock.patch("sqlalchemy.event.listens_for") as mock_listens:
            loader.models.get_engine()
            for call in mock_listens.call_args_list:
                func = call.args[1] if len(call.args) > 1 else call.kwargs.get("function")
                if func is not None and hasattr(func, "__code__"):
                    consts = func.__code__.co_consts
                    if any("PRAGMA" in str(c).upper() for c in consts):
                        pytest.fail(f"发现 SQLite PRAGMA 监听残留: {func!r}")
        # 同时检查源码
        with open(loader.models.__file__) as f:
            models_source = f.read()
        assert "PRAGMA" not in models_source, "models.py 源码不应再出现 PRAGMA"
        assert "journal_mode" not in models_source, "models.py 源码不应再出现 journal_mode"

    def test_no_check_same_thread_connect_args(self, loader):
        """get_engine() 不再传 check_same_thread connect_args。"""
        loader.models.get_engine()
        call_kwargs = loader.mock_create.call_args.kwargs
        connect_args = call_kwargs.get("connect_args", {})
        assert "check_same_thread" not in connect_args, (
            f"create_engine 不应传 check_same_thread, 实际: {connect_args!r}"
        )
        # 同时检查源码
        with open(loader.models.__file__) as f:
            models_source = f.read()
        assert "check_same_thread" not in models_source, (
            "models.py 源码不应再出现 check_same_thread"
        )
