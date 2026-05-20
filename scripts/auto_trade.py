#!/usr/bin/env python3
"""自动跟踪交易执行脚本
读取所有启用了auto_trade的模拟盘账户，检查每一条自动规则，
条件满足时自动下单（不走人工确认）。
"""
import sys
import os

# 确保能找到项目模块
sys.path.insert(0, '/Users/wgfu/work/a-stock-trading')

from models import SessionLocal, PaperAccount, PaperAutoRule, PaperPosition
from paper_trading import create_order, create_snapshot
from datetime import datetime, date
import urllib.request

def get_current_price(code):
    """获取实时价格"""
    sina_code = f"sh{code}" if code.startswith(("5", "6")) else f"sz{code}"
    req = urllib.request.urlopen(f"http://qt.gtimg.cn/q={sina_code}", timeout=8)
    raw = req.read().decode("gbk")
    parts = raw.split("~")
    if len(parts) > 3:
        return float(parts[3])
    return None

def execute_auto_trades():
    """执行所有自动跟踪规则"""
    db = SessionLocal()
    trades = []
    errors = []

    try:
        # 查找所有启用auto_trade的账户
        accounts = db.query(PaperAccount).filter(
            PaperAccount.auto_trade == True,
            PaperAccount.enabled == True
        ).all()

        if not accounts:
            print("没有启用的自动跟踪账户")
            return

        for account in accounts:
            rules = db.query(PaperAutoRule).filter(
                PaperAutoRule.account_id == account.id,
                PaperAutoRule.enabled == True
            ).all()

            if not rules:
                continue

            account_trades = []
            account_errors = []

            for rule in rules:
                current_price = get_current_price(rule.code)
                if current_price is None:
                    account_errors.append(f"{rule.code}: 获取行情失败")
                    continue

                # 检查当前持仓
                position = db.query(PaperPosition).filter(
                    PaperPosition.account_id == account.id,
                    PaperPosition.code == rule.code
                ).first()
                current_shares = position.shares if position else 0

                # ── 买入逻辑 ──
                if rule.buy_enabled:
                    should_buy = False
                    buy_reason = ""

                    if rule.buy_price_low is not None and rule.buy_price_high is not None:
                        if rule.buy_price_low <= current_price <= rule.buy_price_high:
                            should_buy = True
                            buy_reason = f"价格{current_price:.2f}在买入区[{rule.buy_price_low}-{rule.buy_price_high}]"
                    elif rule.buy_price_high is not None:
                        if current_price <= rule.buy_price_high:
                            should_buy = True
                            buy_reason = f"价格{current_price:.2f}<=买入上限{rule.buy_price_high}"

                    # 检查最大持仓限制
                    if should_buy and rule.max_position > 0 and current_shares >= rule.max_position:
                        should_buy = False
                        buy_reason = f"已达最大持仓{rule.max_position}股"

                    if should_buy:
                        try:
                            # 计算可买股数(100的整数倍)
                            cost = rule.buy_quantity * current_price
                            max_by_cash = int(account.cash_balance / current_price / 100) * 100
                            actual_qty = min(rule.buy_quantity, max_by_cash)
                            if rule.max_position > 0:
                                actual_qty = min(actual_qty, rule.max_position - current_shares)

                            if actual_qty >= 100:
                                result = create_order(
                                    account_id=account.id,
                                    code=rule.code,
                                    name=rule.name or "",
                                    direction="buy",
                                    price=current_price,
                                    quantity=actual_qty,
                                    order_type="auto",
                                    note=f"自动跟踪买入: {buy_reason}"
                                )
                                account_trades.append(
                                    f"  ✅ 买入 {rule.code} {rule.name} {actual_qty}股@{current_price:.2f}"
                                )
                        except ValueError as e:
                            account_errors.append(f"{rule.code} 买入失败: {e}")

                # ── 卖出逻辑（止盈/止损） ──
                if rule.sell_enabled and current_shares > 0:
                    should_sell = False
                    sell_reason = ""

                    if rule.sell_target_price is not None and current_price >= rule.sell_target_price:
                        should_sell = True
                        sell_reason = f"止盈: 价格{current_price:.2f}>=目标{rule.sell_target_price}"

                    if rule.sell_stop_loss is not None and current_price <= rule.sell_stop_loss:
                        should_sell = True
                        sell_reason = f"止损: 价格{current_price:.2f}<=止损{rule.sell_stop_loss}"

                    if should_sell:
                        try:
                            result = create_order(
                                account_id=account.id,
                                code=rule.code,
                                name=rule.name or "",
                                direction="sell",
                                price=current_price,
                                quantity=current_shares,
                                order_type="auto",
                                note=f"自动跟踪卖出: {sell_reason}"
                            )
                            account_trades.append(
                                f"  ✅ 卖出 {rule.code} {rule.name} {current_shares}股@{current_price:.2f}"
                            )
                        except ValueError as e:
                            account_errors.append(f"{rule.code} 卖出失败: {e}")

            # 执行快照
            if account_trades:
                try:
                    create_snapshot(account.id)
                except:
                    pass

            if account_trades:
                trades.append(f"📊 {account.name}:")
                trades.extend(account_trades)
            if account_errors:
                trades.append(f"⚠️ {account.name} 错误:")
                trades.extend([f"  {e}" for e in account_errors])

    finally:
        db.close()

    if trades:
        print("自动跟踪交易执行报告")
        print("=" * 40)
        print("\n".join(trades))
    else:
        print("无交易执行")
        sys.exit(0)

if __name__ == "__main__":
    execute_auto_trades()
