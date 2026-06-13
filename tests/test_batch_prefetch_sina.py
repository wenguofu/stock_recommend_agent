"""TDD Red: 复现 batch_prefetch_all.py Sina fallback 写 amount=0/turnover=0 的 bug
修复后这些测试应当全部通过.
"""
import pytest
from unittest.mock import patch, MagicMock

from batch_prefetch_all import (
    _sina_to_records,
    fetch_stock_data,
    enrich_with_tencent_snapshot,
)


# ──────────── 1. _sina_to_records 推算 amount ────────────

class TestSinaToRecordsAmountEstimation:
    """Sina K-line fallback: amount 必须从 close × volume 推算"""

    def test_red_amount_zero_reproduces_bug(self):
        """RED 快照: 修复后此测试转为验证 amount > 0 (即 bug 已修).
        修复前的旧行为 amount=0 不再成立, 此断言已反向."""
        sample = [{
            'day': '2026-06-10', 'open': '89.350', 'high': '90.060',
            'low': '86.780', 'close': '88.030', 'volume': '20434089',
        }]
        rec = _sina_to_records(sample, 5)[0]
        # 修复后: amount > 0 (原 bug 是 amount=0)
        assert rec['amount'] > 0, \
            f"修复后 amount 应 > 0 (close × volume 推算), 实际={rec['amount']}"

    def test_green_amount_equals_close_times_volume(self):
        """GREEN: 修复后期望 amount = close × volume (Sina volume 是股数)"""
        sample = [{
            'day': '2026-06-10', 'open': '89.350', 'high': '90.060',
            'low': '86.780', 'close': '88.030', 'volume': '20434089',
        }]
        rec = _sina_to_records(sample, 5)[0]
        # 88.030 × 20434089 = 1,798,808,953.47 元 ≈ 17.99 亿
        assert rec['amount'] == pytest.approx(88.030 * 20434089, rel=1e-6)

    def test_green_source_marked_estimated(self):
        """GREEN: Sina 兜底 source 标记为 sina-amount-estimated 便于审计"""
        sample = [{
            'day': '2026-06-10', 'open': '89.350', 'high': '90.060',
            'low': '86.780', 'close': '88.030', 'volume': '20434089',
        }]
        rec = _sina_to_records(sample, 5)[0]
        assert rec['source'] == 'sina-amount-estimated'

    def test_green_turnover_kept_zero_for_later_enrich(self):
        """GREEN: turnover 留 0 (Sina K-line 无换手率), 等腾讯快照回填"""
        sample = [{
            'day': '2026-06-10', 'open': '89.350', 'high': '90.060',
            'low': '86.780', 'close': '88.030', 'volume': '20434089',
        }]
        rec = _sina_to_records(sample, 5)[0]
        assert rec['turnover'] == 0

    def test_zero_volume_yields_zero_amount(self):
        """边界: volume=0 (停牌) 时 amount 也应为 0, 不抛异常"""
        sample = [{
            'day': '2026-06-10', 'open': '0', 'high': '0',
            'low': '0', 'close': '0', 'volume': '0',
        }]
        rec = _sina_to_records(sample, 5)[0]
        assert rec['amount'] == 0

    def test_truncates_to_requested_days(self):
        """保留原有行为: records 数量不应超过 days"""
        sample = [
            {'day': f'2026-06-{10-i:02d}', 'open': '1', 'high': '1',
             'low': '1', 'close': '1', 'volume': '100'}
            for i in range(20)
        ]
        out = _sina_to_records(sample, 5)
        assert len(out) == 5


# ──────────── 2. fetch_stock_data 非交易时段判断 ────────────

class TestFetchStockDataTradingTimeWindow:
    """is_trading_time 应覆盖盘后 15:00-15:30"""

    def test_post_close_15_15_is_trading_time(self):
        """盘后 15:15 应仍走 akshare (akshare 此时仍可拉当日数据)"""
        with patch('batch_prefetch_all.datetime') as mock_dt:
            mock_dt.now.return_value = MagicMock(
                weekday=lambda: 2,  # 周三
                hour=15, minute=15,
            )
            # akshare 是运行时 import, 注入到 sys.modules
            import sys
            mock_ak = MagicMock()
            mock_df = MagicMock()
            mock_df.empty = False
            mock_ak.stock_zh_a_hist.return_value = mock_df
            sys.modules['akshare'] = mock_ak
            try:
                with patch('batch_prefetch_all._df_to_records') as mock_conv:
                    mock_conv.return_value = [
                        {'date': '2026-06-10', 'close': 88.0, 'volume': 100,
                         'amount': 8800, 'turnover': 1.0, 'source': 'akshare',
                         'open': 88, 'high': 88, 'low': 88, 'code': ''}
                    ]
                    records = fetch_stock_data('002222', '福晶科技', days=10)
                    assert mock_ak.stock_zh_a_hist.called, \
                        "15:15 仍应尝试 akshare, 不应直接走 Sina fallback"
            finally:
                sys.modules.pop('akshare', None)

    def test_weekend_skips_akshare(self):
        """周末应直接走 Sina (akshare 仍可调用但为空, 此处只验证 akshare 被绕过)"""
        with patch('batch_prefetch_all.datetime') as mock_dt:
            mock_dt.now.return_value = MagicMock(
                weekday=lambda: 5,  # 周六
                hour=10, minute=0,
            )
            import sys
            mock_ak = MagicMock()
            sys.modules['akshare'] = mock_ak
            try:
                with patch('batch_prefetch_all.urllib.request.urlopen') as mock_url:
                    mock_url.return_value.__enter__.return_value.read.return_value = b'[]'
                    records = fetch_stock_data('002222', '福晶科技', days=10)
                    # 周末不走 akshare
                    assert not mock_ak.stock_zh_a_hist.called
            finally:
                sys.modules.pop('akshare', None)


# ──────────── 3. enrich_with_tencent_snapshot 二次回填 ────────────

class TestEnrichWithTencentSnapshot:
    """backtest_data 中 turnover=0 / amount=0 的行应由腾讯快照回填"""

    def test_enrich_backfills_turnover_and_amount(self):
        """模拟 1 个 code, 腾讯返回 turnover=4.36 amount_wan=180221,
        DB 写入应被调用且参数正确"""
        with patch('batch_prefetch_all.urllib.request.urlopen') as mock_url:
            parts = [''] * 50
            parts[1] = 'name'
            parts[3] = '88.03'
            parts[37] = '180221'   # amount_wan (万元)
            parts[38] = '4.36'     # turnover (%)
            parts[44] = '414.0'    # circulate_cap_yi
            parts[45] = '414.0'    # market_cap_yi
            body = '~'.join(parts)
            raw = f'v_sz002222="{body}";\n'.encode('gbk')
            mock_url.return_value.__enter__.return_value.read.return_value = raw

            # enrich_with_tencent_snapshot 内部 from models import SessionLocal
            with patch('models.SessionLocal') as mock_sess_factory:
                mock_db = MagicMock()
                mock_sess_factory.return_value = mock_db
                mock_db.execute.return_value.fetchone.return_value = ('2026-06-10',)

                updated = enrich_with_tencent_snapshot(['002222'])

                assert updated >= 1
                assert mock_url.call_count >= 1

    def test_enrich_skips_on_network_error(self):
        """网络异常时跳过该 code, 不抛异常"""
        with patch('batch_prefetch_all.urllib.request.urlopen') as mock_url:
            mock_url.side_effect = Exception("Connection aborted")
            updated = enrich_with_tencent_snapshot(['002222'])
            assert updated == 0

    def test_enrich_respects_rate_limit(self):
        """多 code 时, 调用间隔 ≥ 0.5s (50只/批约束)"""
        with patch('batch_prefetch_all.urllib.request.urlopen') as mock_url:
            def make_raw(prefix):
                parts = ['0'] * 50
                parts[1] = 'name'
                parts[3] = '1.0'
                parts[37] = '100'   # amount_wan
                parts[38] = '1.0'   # turnover
                parts[44] = '1.0'   # circulate_cap
                parts[45] = '1.0'   # market_cap
                body = '~'.join(parts)
                return f'v_{prefix}="{body}";\n'.encode('gbk')
            mock_url.return_value.__enter__.return_value.read.side_effect = [
                make_raw('sz000001'),
                make_raw('sz000002'),
                make_raw('sz000003'),
            ]

            with patch('batch_prefetch_all.time.sleep') as mock_sleep:
                with patch('models.SessionLocal') as mock_sess_factory:
                    mock_db = MagicMock()
                    mock_sess_factory.return_value = mock_db
                    mock_db.execute.return_value.fetchone.return_value = ('2026-06-10',)

                    enrich_with_tencent_snapshot(['000001', '000002', '000003'])

                    assert mock_sleep.call_count == 3
                    for call in mock_sleep.call_args_list:
                        assert call.args[0] >= 0.5
