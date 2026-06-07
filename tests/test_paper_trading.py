"""
Sprint 3 paper_trading 新增功能测试:
  - 订单去重 (client_order_id 幂等键)
  - 行锁 (SELECT ... FOR UPDATE)
  - 失败-关闭 (fail-closed) 风控
"""
import os
import sys
import pytest
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import SessionLocal, PaperAccount, PaperOrder, PaperPosition


# ── 桩: 跳过实盘价格验证(测试用), 用 monkeypatch 替换 urllib 请求 ──
class _FakeHttpResp:
    def read(self):
        # 返回 600519 价格为 100.0 (便于测试断言)
        return (
            b"var hq_str_sh600519='\xe8\xb4\xb5\xe5\xb7\x9e\xe8\x8c\x85\xe5\x8f\xb0,"
            b"100.0,99.0,100.0,101.0,99.0,100.0,100.0,1234,567,890,"
            b"12.34,5.67,0.89,2026-06-07,...'"
        )
    def __enter__(self):
        return self
    def __exit__(self, *a):
        pass


def _patch_price_check(monkeypatch):
    """把 paper_trading 里的 urllib.request.urlopen 替换为假响应"""
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: _FakeHttpResp())


@pytest.fixture
def db_session():
    """每个测试结束后清理 paper_* 表"""
    s = SessionLocal()
    yield s
    try:
        s.query(PaperOrder).filter(PaperOrder.note == "TEST_AUTO_CLEAN").delete()
        s.query(PaperPosition).filter(PaperPosition.name == "TEST_AUTO_CLEAN").delete()
        s.query(PaperAccount).filter(PaperAccount.name == "TEST_AUTO_CLEAN").delete()
        s.commit()
    finally:
        s.close()


@pytest.fixture
def test_account(db_session):
    """创建测试账户"""
    from paper_trading import create_account
    acc = create_account(name="TEST_AUTO_CLEAN", initial_capital=1000000.0)
    return acc["id"]


class TestOrderDedup:
    """订单去重 (client_order_id 幂等键)"""

    def test_same_client_order_id_returns_existing(self, test_account, db_session, monkeypatch):
        """同一 client_order_id 60s 内第二次调用应返回首条订单, 不创建新订单"""
        _patch_price_check(monkeypatch)
        from paper_trading import create_order

        cid = f"test-{uuid.uuid4().hex[:8]}"
        r1 = create_order(
            account_id=test_account, code="600519", name="TEST_AUTO_CLEAN",
            direction="buy", price=100.0, quantity=10, client_order_id=cid,
        )
        assert r1.get("deduplicated") is not True  # 第一次不算去重

        r2 = create_order(
            account_id=test_account, code="600519", name="TEST_AUTO_CLEAN",
            direction="buy", price=100.0, quantity=10, client_order_id=cid,
        )
        # 第二次应命中去重, 标 deduplicated=True
        assert r2.get("deduplicated") is True, f"Expected dedup hit, got: {r2}"

    def test_different_client_order_ids_create_separate_orders(self, test_account, db_session, monkeypatch):
        """不同 client_order_id 应创建独立订单"""
        _patch_price_check(monkeypatch)
        from paper_trading import create_order

        cid1 = f"test-{uuid.uuid4().hex[:8]}"
        cid2 = f"test-{uuid.uuid4().hex[:8]}"

        r1 = create_order(
            account_id=test_account, code="600519", name="TEST_AUTO_CLEAN",
            direction="buy", price=100.0, quantity=10, client_order_id=cid1,
        )
        r2 = create_order(
            account_id=test_account, code="600519", name="TEST_AUTO_CLEAN",
            direction="buy", price=100.0, quantity=10, client_order_id=cid2,
        )
        # 两条订单 ID 应不同
        assert r1["order"]["id"] != r2["order"]["id"]
        assert r1.get("deduplicated") is not True
        assert r2.get("deduplicated") is not True

    def test_no_client_order_id_does_not_dedup(self, test_account, db_session, monkeypatch):
        """不传 client_order_id 不应去重"""
        _patch_price_check(monkeypatch)
        from paper_trading import create_order

        r1 = create_order(
            account_id=test_account, code="600519", name="TEST_AUTO_CLEAN",
            direction="buy", price=100.0, quantity=10,
        )
        r2 = create_order(
            account_id=test_account, code="600519", name="TEST_AUTO_CLEAN",
            direction="buy", price=100.0, quantity=10,
        )
        assert r1["order"]["id"] != r2["order"]["id"]
        assert r2.get("deduplicated") is not True


class TestInsufficientFunds:
    """余额不足时正确抛出 ValueError"""

    def test_buy_with_insufficient_cash_raises(self, db_session, monkeypatch):
        _patch_price_check(monkeypatch)
        # 关闭风控以测试纯余额检查
        import builtins
        real_import = builtins.__import__
        def fake_import_no_risk(name, *args, **kwargs):
            if "risk_control" in name:
                import types
                mod = types.ModuleType(name)
                mod.validate_order = lambda **kw: type("R", (), {"passed": True, "violations": [], "warnings": []})()
                mod.get_current_exposures = lambda *a, **kw: None
                mod.ConstraintConfig = type("C", (), {})
                sys.modules[name] = mod
                return mod
            return real_import(name, *args, **kwargs)
        monkeypatch.setattr(builtins, "__import__", fake_import_no_risk)

        from paper_trading import create_account, create_order
        acc = create_account(name="TEST_AUTO_CLEAN", initial_capital=1000.0)
        with pytest.raises(ValueError, match=r"余额不足"):
            create_order(
                account_id=acc["id"], code="600519", name="TEST_AUTO_CLEAN",
                direction="buy", price=100.0, quantity=100,  # 需 10000, 远超 1000
            )


class TestFailClosedRiskControl:
    """风控失败时 fail-closed (Sprint1 修复)"""

    def test_risk_control_module_missing_blocks_order(self, monkeypatch, test_account):
        """风控模块导入失败时, 订单应被阻断(不静默放行)"""
        import builtins
        from paper_trading import create_order

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if "risk_control" in name:
                raise ImportError("simulated missing module")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", fake_import)
        # 跳过实盘价格验证
        _patch_price_check(monkeypatch)

        result = create_order(
            account_id=test_account, code="600519", name="TEST_AUTO_CLEAN",
            direction="buy", price=100.0, quantity=10,
        )
        # fail-closed: 必须返 success=False
        assert result.get("success") is False, f"Order should be blocked, got: {result}"
        assert "Risk control" in result.get("error", "") or "blocked" in result.get("error", "").lower()
