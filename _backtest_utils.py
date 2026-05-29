#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
回测共享工具 — A股交易成本模型 + 通用指标计算
供 backtest_engine.py 和 strategy_backtest.py 共同引用
"""
import numpy as np


# ═══════════════════════════════════════════
# A股交易成本模型
# ═══════════════════════════════════════════

class AStockCostModel:
    """A股真实交易成本计算器"""

    def __init__(self, commission_rate=0.00025, min_commission=5.0,
                 stamp_tax_rate=0.001, slippage_bps=10):
        self.commission_rate = commission_rate  # 万2.5
        self.min_commission = min_commission    # 最低5元
        self.stamp_tax_rate = stamp_tax_rate    # 千1 (仅卖出)
        self.slippage_bps = slippage_bps        # 滑点 (bp)

    def buy_cost(self, amount: float) -> dict:
        """买入成本"""
        commission = max(amount * self.commission_rate, self.min_commission)
        slippage = amount * (self.slippage_bps / 10000)
        return {
            'commission': round(commission, 2),
            'slippage': round(slippage, 2),
            'total': round(commission + slippage, 2),
        }

    def sell_cost(self, amount: float) -> dict:
        """卖出成本"""
        commission = max(amount * self.commission_rate, self.min_commission)
        tax = amount * self.stamp_tax_rate
        slippage = amount * (self.slippage_bps / 10000)
        return {
            'commission': round(commission, 2),
            'stamp_tax': round(tax, 2),
            'slippage': round(slippage, 2),
            'total': round(commission + tax + slippage, 2),
        }

    def round_lot(self, shares: int) -> int:
        """向下取整到100股 (A股最小交易单位)"""
        return int(shares / 100) * 100

    def exec_buy_price(self, base_price: float) -> float:
        """买方执行价 (含滑点)"""
        return base_price * (1 + self.slippage_bps / 10000)

    def exec_sell_price(self, base_price: float) -> float:
        """卖方执行价 (含滑点)"""
        return base_price * (1 - self.slippage_bps / 10000)


# 单例
DEFAULT_COST_MODEL = AStockCostModel()


# ═══════════════════════════════════════════
# 通用回测指标
# ═══════════════════════════════════════════

def compute_trade_metrics(trades: list, initial_capital: float = 100000) -> dict:
    """从交易记录计算核心指标"""
    if not trades:
        return {
            'total_trades': 0,
            'win_rate': 0,
            'avg_return': 0,
            'total_return': 0,
        }

    wins = [t for t in trades if t.get('is_win', False)]
    returns = [t.get('pnl_pct', 0) for t in trades]
    win_rate = len(wins) / len(trades) * 100

    return {
        'total_trades': len(trades),
        'wins': len(wins),
        'losses': len(trades) - len(wins),
        'win_rate': round(win_rate, 1),
        'avg_return': round(np.mean(returns), 2) if returns else 0,
        'avg_win': round(np.mean([t.get('pnl_pct', 0) for t in wins]), 2) if wins else 0,
        'avg_loss': round(np.mean([t.get('pnl_pct', 0) for t in trades if not t.get('is_win', False)]), 2),
        'total_return': round(sum(returns), 2),
        'max_return': round(max(returns), 2) if returns else 0,
        'min_return': round(min(returns), 2) if returns else 0,
    }


def compute_equity_metrics(equity_curve: list) -> dict:
    """从净值曲线计算风险指标"""
    if len(equity_curve) < 2:
        return {}

    values = [e.get('total_value', 0) for e in equity_curve]
    values = np.array(values)

    returns = np.diff(values) / values[:-1]
    returns = returns[~np.isnan(returns)]

    if len(returns) < 10:
        return {}

    # 最大回撤
    peak = values[0]
    max_dd = 0
    for v in values:
        if v > peak:
            peak = v
        dd = (peak - v) / peak
        if dd > max_dd:
            max_dd = dd

    # 夏普比率
    mu = np.mean(returns)
    sigma = np.std(returns)
    sharpe = (mu / sigma * np.sqrt(252)) if sigma > 0 else 0

    # 年化收益
    days = len(equity_curve)
    total_return = (values[-1] / values[0] - 1)
    annual_return = (1 + total_return) ** (252 / days) - 1 if days > 0 else 0

    return {
        'total_return_pct': round(total_return * 100, 2),
        'annual_return_pct': round(annual_return * 100, 2),
        'max_drawdown_pct': round(max_dd * 100, 2),
        'sharpe_ratio': round(sharpe, 4),
        'volatility_pct': round(sigma * np.sqrt(252) * 100, 2),
        'trading_days': days,
    }
