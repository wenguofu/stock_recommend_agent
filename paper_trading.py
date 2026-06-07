#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""模拟盘交易核心逻辑

本模块提供模拟盘账户管理、下单交易、快照记录、收益分析等完整功能。
所有函数返回可 JSON 序列化的 dict，而非 ORM 对象。
"""

import logging
import traceback
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

logger = logging.getLogger('paper_trading')

from business_config import cfg  # 业务配置中心化 (Sprint3)

from models import (
    SessionLocal,
    PaperAccount,
    PaperPosition,
    PaperOrder,
    PaperSnapshot,
    EtfReplacementMap,
)


# ═══════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════

def _to_dict(obj) -> dict:
    """将 ORM 对象转为可 JSON 序列化的 dict，datetime 转为 isoformat 字符串"""
    result = {}
    for column in obj.__table__.columns:
        val = getattr(obj, column.name)
        if isinstance(val, datetime):
            val = val.isoformat()
        result[column.name] = val
    return result


def _get_etf_replacement(db, code: str, account: PaperAccount) -> Optional[Dict]:
    """
    查找 ETF 替代映射。
    对 "688" 开头的科创板股票，查找 EtfReplacementMap 获取对应的 ETF。
    如果找不到映射但账户启用了 include_etf_replacement，则自动创建默认映射。
    返回 {"etf_code": str, "etf_name": str, "replaced": bool, "original_code": str, "original_name": str}
    """
    if not str(code).startswith("688"):
        return None

    # 查找已有映射
    mapping = db.query(EtfReplacementMap).filter(
        EtfReplacementMap.original_code == code
    ).first()

    if mapping:
        return {
            "etf_code": mapping.etf_code,
            "etf_name": mapping.etf_name or "",
            "replaced": True,
            "original_code": code,
            "original_name": mapping.original_name or "",
        }

    # 没有映射但账户开启了 ETF 替代 → 自动创建默认映射
    if account.include_etf_replacement:
        default_etf_code = "588000"
        default_etf_name = "科创50ETF"
        try:
            new_map = EtfReplacementMap(
                original_code=code,
                original_name="",
                etf_code=default_etf_code,
                etf_name=default_etf_name,
                ratio=1.0,
            )
            db.add(new_map)
            db.commit()
            db.refresh(new_map)
            return {
                "etf_code": default_etf_code,
                "etf_name": default_etf_name,
                "replaced": True,
                "original_code": code,
                "original_name": "",
            }
        except Exception as e:
            logger.warning(f"[PaperTrading] 自动创建ETF映射失败 {code}: {e}")
            return None

    return None


# ═══════════════════════════════════════════════════════════════════
# 1. 创建模拟盘账户
# ═══════════════════════════════════════════════════════════════════

def create_account(
    name: str,
    strategy_id: Optional[int] = None,
    initial_capital: float = 1000000,
) -> Dict[str, Any]:
    """创建模拟盘账户，返回账户 dict"""
    db = SessionLocal()
    try:
        account = PaperAccount(
            name=name,
            strategy_id=strategy_id,
            initial_capital=initial_capital,
            cash_balance=initial_capital,
            total_market_value=0,
            total_profit_pct=0,
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        return _to_dict(account)
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════
# 2. 创建交易订单（核心交易函数）
# ═══════════════════════════════════════════════════════════════════

def create_order(
    account_id: int,
    code: str,
    name: str,
    direction: str,
    price: float,
    quantity: int,
    order_type: str = "manual",
    strategy_run_id: Optional[str] = None,
    note: Optional[str] = None,
    client_order_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    创建模拟盘交易订单。

    处理流程：
      0. 客户端去重: 若传 client_order_id, 在 DEDUP_WINDOW 秒内命中既有订单则幂等返回
      1. ETF 替代检查（688 开头科创板股票）
      2. 买入：计算佣金、检查余额、更新持仓
      3. 卖出：检查持仓、计算佣金和印花税、更新现金和持仓
      4. 记录订单、更新账户总市值和收益率
      5. 关键行加 SELECT ... FOR UPDATE 防止并发超扣

    返回 {"order": ..., "account": ..., "position": ...}
    """
    # ── 客户端去重 (幂等) ──
    DEDUP_WINDOW_SEC = 60  # 60 秒内同 client_order_id 视为重复
    if client_order_id:
        db = SessionLocal()
        try:
            existing = db.query(PaperOrder).filter(
                PaperOrder.account_id == account_id,
                PaperOrder.client_order_id == client_order_id,
                PaperOrder.created_at >= datetime.now() - timedelta(seconds=DEDUP_WINDOW_SEC),
            ).order_by(PaperOrder.id.desc()).first()
            if existing:
                logger.info(f"订单去重命中: client_order_id={client_order_id} → order_id={existing.id}")
                position = db.query(PaperPosition).filter(
                    PaperPosition.account_id == account_id,
                    PaperPosition.code == existing.code,
                ).first()
                account = db.query(PaperAccount).filter(PaperAccount.id == account_id).first()
                return {
                    "order": _to_dict(existing),
                    "account": _to_dict(account) if account else None,
                    "position": _to_dict(position) if position else None,
                    "deduplicated": True,
                }
        finally:
            db.close()

    db = SessionLocal()
    try:
        # ── 加载账户 (行锁, 防并发超扣) ──
        account = db.query(PaperAccount).filter(
            PaperAccount.id == account_id
        ).with_for_update().first()
        if not account:
            raise ValueError(f"模拟盘账户不存在: {account_id}")

        # ── ETF 替代检查 ──
        etf_info = _get_etf_replacement(db, code, account)
        effective_code = code
        etf_replaced = False
        original_code = None

        if etf_info:
            effective_code = etf_info["etf_code"]
            etf_replaced = True
            original_code = etf_info["original_code"]

        # ── 实盘价格验证 ──
        try:
            import urllib.request, json
            sina_code = f"sh{effective_code}" if effective_code.startswith(("5", "6")) else f"sz{effective_code}"
            url = f"http://qt.gtimg.cn/q={sina_code}"
            req = urllib.request.urlopen(url, timeout=5)
            raw = req.read().decode("gbk")
            parts = raw.split("~")
            if len(parts) > 3:
                market_price = float(parts[3])
                # 价格容差: 交易时段3%, 非交易时段5%
                from scheduler import is_trading_hours
                tolerance = 0.03 if is_trading_hours() else 0.05
                deviation = abs(price - market_price) / market_price
                if deviation > tolerance:
                    raise ValueError(
                        f"实盘价格验证失败: 下单价 {price:.2f} 与当前市场价 {market_price:.2f} "
                        f"偏差 {deviation*100:.1f}%，超过允许范围 {tolerance*100:.0f}%。"
                        f"请使用接近当前行情的价格下单"
                    )
        except ValueError:
            raise
        except Exception as e:
            # 网络异常时放宽检查，但记录警告
            logger.warning(f"[警告] 实盘价格验证失败，跳过检查: {e}")

        # === AI Risk Control: Hard constraint validation ===
        try:
            from risk_control.hard_constraints import validate_order, ConstraintConfig
            from risk_control.position_guard import get_current_exposures

            exposures = get_current_exposures(account_id)
            if exposures:
                sector = 'default'
                # Determine sector from code prefix
                prefix = code[:2] if len(code) >= 2 else ''
                sector_map = {
                    '60': 'Shanghai', '68': 'STAR',
                    '00': 'Shenzhen', '30': 'ChiNext',
                }
                sector = sector_map.get(prefix, 'Other')

                # Build sector exposure map
                sector_exposure = {}
                for pos in exposures.get('positions', []):
                    p_code = pos.get('code', '')
                    p_prefix = p_code[:2] if len(p_code) >= 2 else ''
                    p_sector = sector_map.get(p_prefix, 'Other')
                    sector_exposure[p_sector] = sector_exposure.get(p_sector, 0) + pos.get('market_value', 0)

                result = validate_order(
                    action='buy' if direction == 'buy' else 'sell',
                    target_code=code,
                    target_sector=sector,
                    order_amount=price * quantity,
                    portfolio_value=exposures.get('portfolio_value', 100000),
                    current_positions=exposures.get('positions', []),
                    sector_exposure_map=sector_exposure,
                    current_daily_pnl_pct=exposures.get('daily_pnl_pct', 0),
                )

                if not result.passed:
                    error_msg = '; '.join(result.violations)
                    logger.warning(f"Risk control blocked order for {code}: {error_msg}")
                    # Return error to caller
                    return {
                        'success': False,
                        'error': f'Risk control: {error_msg}',
                        'violations': result.violations,
                        'warnings': result.warnings,
                    }
        except ImportError as e:
            # ImportError: 风控模块未安装,默认 fail-closed,阻断订单
            logger.error(f"Risk control module import failed (BLOCKING order): {e}")
            return {
                'success': False,
                'error': f'Risk control unavailable: {e}. Order blocked for safety.',
            }
        except Exception as e:
            # Runtime error: fail-closed 模式,阻断订单并告警
            logger.error(f"Risk control check failed (BLOCKING order): {e}", exc_info=True)
            return {
                'success': False,
                'error': f'Risk control check failed: {e}. Order blocked for safety.',
            }
        # === End AI Risk Control ===

        # ── 计算费用 ──
        amount = price * quantity

        if direction == "buy":
            # 买入：万2.5佣金(由 business_config 中心化), 最低5元, 无印花税
            commission = max(amount * cfg.trading.commission_rate, cfg.trading.commission_min)
            tax = 0.0
            total_cost = amount + commission

            if account.cash_balance < total_cost:
                raise ValueError(
                    f"余额不足：需要 {total_cost:.2f}，当前现金 {account.cash_balance:.2f}"
                )

            # 扣减现金
            account.cash_balance -= total_cost

            # ── 查找或创建持仓 (行锁, 防并发) ──
            position = db.query(PaperPosition).filter(
                PaperPosition.account_id == account_id,
                PaperPosition.code == effective_code,
            ).with_for_update().first()

            if position:
                # 更新平均成本：加权平均
                old_total = position.avg_cost * position.shares
                position.avg_cost = (old_total + amount) / (position.shares + quantity)
                position.shares += quantity
            else:
                position = PaperPosition(
                    account_id=account_id,
                    code=effective_code,
                    name=name,
                    shares=quantity,
                    avg_cost=price,
                    current_price=price,
                    etf_replaced=etf_replaced,
                    original_code=original_code if etf_replaced else None,
                )
                db.add(position)

            # 更新持仓市值
            position.current_price = price
            position.market_value = position.shares * price
            position.profit_pct = (
                (price - position.avg_cost) / position.avg_cost * 100
                if position.avg_cost > 0
                else 0
            )

            db.flush()  # 确保 position.id 可用

        elif direction == "sell":
            # 卖出：万2.5佣金，最低5元；万10印花税
            position = db.query(PaperPosition).filter(
                PaperPosition.account_id == account_id,
                PaperPosition.code == effective_code,
            ).with_for_update().first()

            if not position:
                raise ValueError(f"未找到持仓: {effective_code}")
            if position.shares < quantity:
                raise ValueError(
                    f"持仓不足：需要 {quantity} 股，当前 {position.shares} 股"
                )

            commission = max(amount * cfg.trading.commission_rate, cfg.trading.commission_min)
            tax = amount * cfg.trading.stamp_tax_rate  # 印花税
            total_income = amount - commission - tax

            # 增加现金
            account.cash_balance += total_income

            # 更新持仓
            position.shares -= quantity

            if position.shares == 0:
                # 清仓：删除持仓
                db.delete(position)
                position = None
            else:
                position.current_price = price
                position.market_value = position.shares * price
                position.profit_pct = (
                    (price - position.avg_cost) / position.avg_cost * 100
                    if position.avg_cost > 0
                    else 0
                )

            db.flush()

        else:
            raise ValueError(f"无效的交易方向: {direction}（应为 buy 或 sell）")

        # ── 记录订单 ──
        order = PaperOrder(
            account_id=account_id,
            code=code,  # 记录原始用户输入的代码
            name=name,
            direction=direction,
            price=price,
            quantity=quantity,
            amount=amount,
            commission=commission,
            tax=tax,
            order_type=order_type,
            strategy_run_id=strategy_run_id,
            note=note,
            client_order_id=client_order_id,
        )
        db.add(order)
        db.flush()

        # ── 更新账户总市值和收益率 ──
        positions = db.query(PaperPosition).filter(
            PaperPosition.account_id == account_id
        ).all()
        total_market_value = sum(
            (p.shares * p.current_price) for p in positions if p.shares > 0
        )
        account.total_market_value = total_market_value
        account.total_profit_pct = (
            (account.cash_balance + total_market_value - account.initial_capital)
            / account.initial_capital
            * 100
        )
        account.updated_at = datetime.now()

        db.commit()

        # 刷新以获取最新的数据库状态
        db.refresh(account)
        db.refresh(order)
        if direction == "buy" or (direction == "sell" and position is not None):
            db.refresh(position)

        # 构造返回结果
        result = {
            "order": _to_dict(order),
            "account": _to_dict(account),
            "position": _to_dict(position) if position else None,
        }
        return result

    except ValueError as e:
        db.rollback()
        raise e
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise RuntimeError(f"创建订单失败: {e}")
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════
# 3. 创建账户快照
# ═══════════════════════════════════════════════════════════════════

def create_snapshot(account_id: int) -> Dict[str, Any]:
    """
    创建模拟盘账户快照。

    刷新所有持仓的当前价格（调用实时行情接口），
    计算总资产、市值、当日盈亏，保存快照记录。
    """
    db = SessionLocal()
    try:
        account = db.query(PaperAccount).filter(PaperAccount.id == account_id).first()
        if not account:
            raise ValueError(f"模拟盘账户不存在: {account_id}")

        # 先刷新持仓价格
        _refresh_positions_prices(db, account_id)

        # 重新查询持仓（刷新后数据已更新）
        positions = db.query(PaperPosition).filter(
            PaperPosition.account_id == account_id
        ).all()

        total_market_value = sum(
            (p.shares * p.current_price) for p in positions if p.shares > 0
        )

        # 计算当日盈亏：基于最近一次快照
        last_snapshot = (
            db.query(PaperSnapshot)
            .filter(PaperSnapshot.account_id == account_id)
            .order_by(PaperSnapshot.snapshot_time.desc())
            .first()
        )

        current_total_value = account.cash_balance + total_market_value
        prev_total_value = last_snapshot.total_value if last_snapshot else account.initial_capital

        daily_pnl = current_total_value - prev_total_value
        daily_pnl_pct = (daily_pnl / prev_total_value * 100) if prev_total_value > 0 else 0

        # 更新账户汇总
        account.total_market_value = total_market_value
        account.total_profit_pct = (
            (account.cash_balance + total_market_value - account.initial_capital)
            / account.initial_capital
            * 100
        )
        account.updated_at = datetime.now()

        # 创建快照
        snapshot = PaperSnapshot(
            account_id=account_id,
            snapshot_time=datetime.now(),
            total_value=current_total_value,
            cash_balance=account.cash_balance,
            market_value=total_market_value,
            daily_pnl=daily_pnl,
            daily_pnl_pct=daily_pnl_pct,
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)

        return _to_dict(snapshot)

    except ValueError as e:
        db.rollback()
        raise e
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise RuntimeError(f"创建快照失败: {e}")
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════
# 4. 计算账户统计
# ═══════════════════════════════════════════════════════════════════

def calculate_account_stats(account_id: int) -> Dict[str, Any]:
    """重新计算账户统计信息：总市值、收益率、胜率、最大回撤"""
    db = SessionLocal()
    try:
        account = db.query(PaperAccount).filter(PaperAccount.id == account_id).first()
        if not account:
            raise ValueError(f"模拟盘账户不存在: {account_id}")

        # 总市值
        positions = db.query(PaperPosition).filter(
            PaperPosition.account_id == account_id
        ).all()
        total_market_value = sum(
            (p.shares * p.current_price) for p in positions if p.shares > 0
        )

        # 总收益率
        total_value = account.cash_balance + total_market_value
        total_profit_pct = (
            (total_value - account.initial_capital) / account.initial_capital * 100
            if account.initial_capital > 0
            else 0
        )

        # 胜率：基于已完成的卖出订单
        win_rate = _calculate_win_rate_internal(db, account_id)

        # 最大回撤：基于所有快照
        max_drawdown = _calculate_max_drawdown(db, account_id)

        # 写入账户
        account.total_market_value = total_market_value
        account.total_profit_pct = total_profit_pct
        account.win_rate = win_rate
        account.max_drawdown = max_drawdown
        account.updated_at = datetime.now()
        db.commit()
        db.refresh(account)

        return _to_dict(account)

    except ValueError as e:
        db.rollback()
        raise e
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise RuntimeError(f"计算账户统计失败: {e}")
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════
# 5. 计算胜率
# ═══════════════════════════════════════════════════════════════════

def calculate_win_rate(account_id: int) -> float:
    """
    计算账户胜率。

    基于所有已完成的卖出订单，判断每次卖出是否盈利。
    胜率 = 盈利卖出次数 / 总卖出次数 × 100%
    """
    db = SessionLocal()
    try:
        return _calculate_win_rate_internal(db, account_id)
    finally:
        db.close()


def _calculate_win_rate_internal(db, account_id: int) -> float:
    """内部胜率计算（使用已有 session）"""
    sell_orders = (
        db.query(PaperOrder)
        .filter(
            PaperOrder.account_id == account_id,
            PaperOrder.direction == "sell",
        )
        .order_by(PaperOrder.created_at.asc())
        .all()
    )

    if not sell_orders:
        return 0.0

    # 对每次卖出，通过比较卖出金额与买入成本估算盈利
    profitable = 0
    total_sells = len(sell_orders)

    for sell in sell_orders:
        # 找到该卖出之前的所有买入订单（同一 code）
        buy_orders = (
            db.query(PaperOrder)
            .filter(
                PaperOrder.account_id == account_id,
                PaperOrder.code == sell.code,
                PaperOrder.direction == "buy",
                PaperOrder.created_at < sell.created_at,
            )
            .order_by(PaperOrder.created_at.asc())
            .all()
        )

        if not buy_orders:
            # 没有买入记录，跳过（如初始持仓直接卖出）
            continue

        # 用买入订单的加权平均价格估算成本
        total_buy_amount = sum(b.price * b.quantity for b in buy_orders)
        total_buy_qty = sum(b.quantity for b in buy_orders)
        avg_buy_price = total_buy_amount / total_buy_qty if total_buy_qty > 0 else 0

        # 卖出收入（扣除佣金和印花税）= sell.price * sell.quantity - sell.commission - sell.tax
        sell_income = sell.price * sell.quantity - sell.commission - sell.tax
        sell_cost = avg_buy_price * sell.quantity

        if sell_income > sell_cost:
            profitable += 1

    return round(profitable / total_sells * 100, 2)


def _calculate_max_drawdown(db, account_id: int) -> float:
    """计算最大回撤（百分比），基于快照数据"""
    snapshots = (
        db.query(PaperSnapshot)
        .filter(PaperSnapshot.account_id == account_id)
        .order_by(PaperSnapshot.snapshot_time.asc())
        .all()
    )

    if not snapshots:
        return 0.0

    peak = snapshots[0].total_value
    max_dd = 0.0

    for snap in snapshots:
        if snap.total_value > peak:
            peak = snap.total_value
        dd = (peak - snap.total_value) / peak * 100 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd

    return round(max_dd, 2)


# ═══════════════════════════════════════════════════════════════════
# 6. 获取账户摘要
# ═══════════════════════════════════════════════════════════════════

def get_account_summary(account_id: int) -> Dict[str, Any]:
    """
    获取账户完整摘要信息。

    包含：名称、初始资金、现金、市值、总资产、收益率、
          最大回撤、胜率、持仓数、快照数、订单数
    """
    db = SessionLocal()
    try:
        account = db.query(PaperAccount).filter(PaperAccount.id == account_id).first()
        if not account:
            raise ValueError(f"模拟盘账户不存在: {account_id}")

        # 持仓数（有实际持仓的）
        position_count = (
            db.query(PaperPosition)
            .filter(
                PaperPosition.account_id == account_id,
                PaperPosition.shares > 0,
            )
            .count()
        )

        snapshot_count = (
            db.query(PaperSnapshot)
            .filter(PaperSnapshot.account_id == account_id)
            .count()
        )

        order_count = (
            db.query(PaperOrder)
            .filter(PaperOrder.account_id == account_id)
            .count()
        )

        total_value = account.cash_balance + (account.total_market_value or 0)

        return {
            "id": account.id,
            "name": account.name,
            "initial_capital": account.initial_capital,
            "cash_balance": account.cash_balance,
            "total_market_value": account.total_market_value or 0,
            "total_value": total_value,
            "total_profit_pct": account.total_profit_pct or 0,
            "max_drawdown": account.max_drawdown or 0,
            "win_rate": account.win_rate or 0,
            "position_count": position_count,
            "snapshot_count": snapshot_count,
            "order_count": order_count,
            "created_at": account.created_at.isoformat() if account.created_at else None,
            "updated_at": account.updated_at.isoformat() if account.updated_at else None,
        }

    except ValueError as e:
        raise e
    except Exception as e:
        traceback.print_exc()
        raise RuntimeError(f"获取账户摘要失败: {e}")
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════
# 7. 刷新持仓价格
# ═══════════════════════════════════════════════════════════════════

def refresh_prices(account_id: int) -> List[Dict[str, Any]]:
    """
    刷新模拟盘账户所有持仓的当前价格。

    调用新浪实时行情接口更新每个持仓的 current_price，
    并重新计算 market_value 和 profit_pct。
    返回更新后的持仓列表。
    """
    db = SessionLocal()
    try:
        account = db.query(PaperAccount).filter(PaperAccount.id == account_id).first()
        if not account:
            raise ValueError(f"模拟盘账户不存在: {account_id}")

        updated = _refresh_positions_prices(db, account_id)
        db.commit()

        # 刷新后重新查询，返回更新后数据
        positions = db.query(PaperPosition).filter(
            PaperPosition.account_id == account_id
        ).all()

        return [_to_dict(p) for p in positions]

    except ValueError as e:
        db.rollback()
        raise e
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise RuntimeError(f"刷新价格失败: {e}")
    finally:
        db.close()


def _refresh_positions_prices(db, account_id: int) -> int:
    """
    内部函数：刷新账户所有持仓的价格。

    调用 data_fetchers.get_realtime_data 获取实时价格，
    更新持仓的 current_price、market_value、profit_pct。
    返回成功更新的持仓数。
    """
    positions = db.query(PaperPosition).filter(
        PaperPosition.account_id == account_id,
        PaperPosition.shares > 0,
    ).all()

    updated_count = 0

    for pos in positions:
        try:
            # 动态导入，避免循环依赖
            from data_fetchers import get_realtime_data

            code_to_fetch = pos.code
            realtime = get_realtime_data(code_to_fetch)

            if realtime is None:
                # 获取失败，跳过该持仓
                continue

            # 兼容多种键名：current_price 或 price
            current_price = realtime.get("current_price") or realtime.get("price")
            if current_price is None:
                continue

            pos.current_price = current_price
            pos.market_value = pos.shares * current_price
            pos.profit_pct = (
                (current_price - pos.avg_cost) / pos.avg_cost * 100
                if pos.avg_cost > 0
                else 0
            )
            pos.updated_at = datetime.now()
            updated_count += 1

        except ImportError:
            # data_fetchers 不可用，静默跳过
            continue
        except Exception as e:
            logger.warning(f"[PaperTrading] 刷新价格失败 {pos.code}: {e}")
            continue

    # 更新账户总市值
    account = db.query(PaperAccount).filter(PaperAccount.id == account_id).first()
    if account:
        total_market_value = sum(
            (p.shares * p.current_price) for p in positions if p.shares > 0
        )
        account.total_market_value = total_market_value
        account.total_profit_pct = (
            (account.cash_balance + total_market_value - account.initial_capital)
            / account.initial_capital
            * 100
        )
        account.updated_at = datetime.now()

    return updated_count


# ═══════════════════════════════════════════════════════════════════
# 8. 获取收益曲线
# ═══════════════════════════════════════════════════════════════════

def get_equity_curve(account_id: int, limit: int = 200) -> List[Dict[str, Any]]:
    """
    获取账户净值曲线数据。

    按快照时间倒序获取最近 N 条快照记录，
    返回 dict 列表供前端图表渲染。
    """
    db = SessionLocal()
    try:
        snapshots = (
            db.query(PaperSnapshot)
            .filter(PaperSnapshot.account_id == account_id)
            .order_by(PaperSnapshot.snapshot_time.desc())
            .limit(limit)
            .all()
        )

        # 倒序后正序排列，方便图表从左到右渲染
        snapshots.reverse()

        return [_to_dict(s) for s in snapshots]

    except Exception as e:
        traceback.print_exc()
        raise RuntimeError(f"获取收益曲线失败: {e}")
    finally:
        db.close()
