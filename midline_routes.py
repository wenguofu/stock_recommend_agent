#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
中长线交易 API — 为小资金散户设计的简洁接口

端点:
  GET  /api/midline/watchlist-health   — 自选池趋势健康度评分
  GET  /api/midline/signals/<code>     — 三信号灯 (MA排列/MACD/RSI)
  POST /api/midline/position-calc      — 仓位计算器
  GET  /api/midline/journal            — 交易日志列表
  POST /api/midline/journal            — 记录交易
  PUT  /api/midline/journal/<id>       — 更新记录
  DELETE /api/midline/journal/<id>     — 删除记录
"""

from flask import jsonify, request
import json
from datetime import datetime


def register_midline_routes(app):
    """注册中长线 API 路由"""

    # ═══════════════════════════════════════════
    # 自选池健康度
    # ═══════════════════════════════════════════

    @app.route("/api/midline/watchlist-health")
    def midline_watchlist_health():
        """对自选池每只股票打分：趋势强度(满分100)"""
        page = request.args.get('page', 1, type=int)
        pageSize = request.args.get('pageSize', 20, type=int)

        from models import SessionLocal
        from db import get_watchlist

        db = SessionLocal()
        try:
            items = get_watchlist(db)
            results = []
            for item in items:
                try:
                    score = _score_stock(item.code)

                    # Try to get DL prediction
                    dl_direction = None
                    dl_prob_up = None
                    dl_prob_down = None
                    dl_short_return = None
                    try:
                        from factor_engine import get_feature_vector
                        fv = get_feature_vector(item.code)
                        if fv and len(fv.get('daily_features', [])) >= 30:
                            from dl_models.short_term_predictor import ShortTermPredictor
                            import os
                            model_path = os.path.join(app.root_path, '..', 'model_checkpoints', 'short_term_latest.pt')
                            model_path = os.path.normpath(model_path)
                            if os.path.exists(model_path):
                                short_model = ShortTermPredictor.load(model_path)
                                result = short_model.predict(fv['daily_features'], [0.33, 0.33, 0.34])
                                dl_direction = result.get('direction')
                                dl_prob_up = result.get('prob_up')
                                dl_prob_down = result.get('prob_down')
                                dl_short_return = result.get('expected_return')
                    except Exception:
                        pass  # DL not available, leave as None

                    results.append({
                        "code": item.code,
                        "name": item.name,
                        "cost_price": item.cost_price,
                        "shares": item.shares,
                        "score": score["total"],
                        "ma_score": score["ma_score"],
                        "macd_signal": score["macd_signal"],
                        "rsi_score": score["rsi_score"],
                        "trend": score["trend"],
                        "suggestion": score["suggestion"],
                        "dl_direction": dl_direction,
                        "dl_prob_up": dl_prob_up,
                        "dl_prob_down": dl_prob_down,
                        "dl_short_return": dl_short_return,
                    })
                except Exception:
                    results.append({
                        "code": item.code,
                        "name": item.name,
                        "cost_price": item.cost_price,
                        "shares": item.shares,
                        "score": 0,
                        "error": "数据获取失败",
                        "dl_direction": None,
                        "dl_prob_up": None,
                        "dl_prob_down": None,
                        "dl_short_return": None,
                    })
            results.sort(key=lambda x: x["score"], reverse=True)

            total = len(results)
            start = (page - 1) * pageSize
            paginated = results[start:start + pageSize]

            return jsonify({
                "data": paginated,
                "total": total,
                "page": page,
                "pageSize": pageSize,
            })
        finally:
            db.close()

    # ═══════════════════════════════════════════
    # 三信号灯
    # ═══════════════════════════════════════════

    @app.route("/api/midline/signals/<code>")
    def midline_signals(code):
        """返回三信号灯状态"""
        try:
            score = _score_stock(code)
            kline = _get_daily_kline(code, 120)
            current_price = kline[-1]["close"] if kline else 0
            return jsonify({
                "code": code,
                "price": current_price,
                **score,
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ═══════════════════════════════════════════
    # 仓位计算器
    # ═══════════════════════════════════════════

    @app.route("/api/midline/position-calc", methods=["POST"])
    def midline_position_calc():
        """
        输入: total_capital, risk_pct, entry_price, stop_loss_price
        输出: 建议股数、风险金额、盈亏比
        """
        data = request.get_json() or {}
        total = float(data.get("total_capital", 100000))
        risk_pct = float(data.get("risk_pct", 2))  # 每笔风险占总资金%
        entry = float(data.get("entry_price", 0))
        stop = float(data.get("stop_loss_price", 0))
        target = float(data.get("target_price", 0))
        code = data.get('code', '000001')
        sector = data.get('sector', 'Other')
        turnover = data.get('turnover')

        if entry <= 0:
            return jsonify({'error': '入场价必须大于0'}), 400
        if stop is not None and stop <= 0:
            return jsonify({'error': '止损价必须大于0'}), 400
        if target is not None and target <= 0:
            return jsonify({'error': '目标价必须大于0'}), 400

        risk_per_share = abs(entry - stop)
        max_loss = total * (risk_pct / 100)
        shares = int(max_loss / risk_per_share / 100) * 100  # 整百股

        if shares < 100:
            shares = 100

        position_value = shares * entry
        position_pct = (position_value / total) * 100

        result = {
            "total_capital": total,
            "risk_pct": risk_pct,
            "max_loss_amount": round(max_loss, 0),
            "entry_price": entry,
            "stop_loss_price": stop,
            "risk_per_share": round(risk_per_share, 2),
            "suggested_shares": shares,
            "position_value": round(position_value, 0),
            "position_pct": round(position_pct, 1),
        }

        if target > 0:
            reward = target - entry
            risk_rr = reward / risk_per_share if risk_per_share > 0 else 0
            result["target_price"] = target
            result["reward_per_share"] = round(reward, 2)
            result["risk_reward_ratio"] = round(risk_rr, 2)

        # Apply AI risk constraints
        try:
            from risk_control.hard_constraints import validate_order, ConstraintConfig
            config = ConstraintConfig()
            r = validate_order(
                action='buy',
                target_code=code,
                target_sector=sector,
                order_amount=position_value,
                portfolio_value=total,
                current_positions=[],
                current_daily_pnl_pct=0,
                avg_daily_turnover=turnover,
            )
            result['risk_check'] = {
                'passed': r.passed,
                'violations': r.violations,
                'warnings': r.warnings,
            }
        except ImportError:
            result['risk_check'] = None

        return jsonify(result)

    # ═══════════════════════════════════════════
    # 交易日志 CRUD
    # ═══════════════════════════════════════════

    @app.route("/api/midline/journal", methods=["GET", "POST"])
    def midline_journal():
        from models import SessionLocal
        db = SessionLocal()
        try:
            if request.method == "GET":
                page = request.args.get('page', 1, type=int)
                pageSize = request.args.get('pageSize', 15, type=int)

                total_row = db.execute("SELECT COUNT(*) FROM trade_journal").fetchone()
                total = total_row[0] if total_row else 0

                offset = (page - 1) * pageSize
                rows = db.execute(
                    "SELECT * FROM trade_journal ORDER BY entry_date DESC LIMIT ? OFFSET ?",
                    (pageSize, offset)
                ).fetchall()
                return jsonify({
                    "data": [dict(r) for r in rows],
                    "total": total,
                    "page": page,
                    "pageSize": pageSize,
                })

            if request.method == "POST":
                data = request.get_json() or {}
                db.execute(
                    """INSERT INTO trade_journal
                       (code, name, direction, entry_date, entry_price, shares,
                        stop_loss, target_price, exit_date, exit_price, pnl, pnl_pct,
                        reason_entry, reason_exit, notes, tags)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        data.get("code"),
                        data.get("name"),
                        data.get("direction", "long"),
                        data.get("entry_date"),
                        data.get("entry_price"),
                        data.get("shares"),
                        data.get("stop_loss"),
                        data.get("target_price"),
                        data.get("exit_date"),
                        data.get("exit_price"),
                        data.get("pnl"),
                        data.get("pnl_pct"),
                        data.get("reason_entry"),
                        data.get("reason_exit"),
                        data.get("notes"),
                        data.get("tags"),
                    ),
                )
                db.commit()
                return jsonify({"message": "已记录"})
        finally:
            db.close()

    @app.route("/api/midline/journal/<int:journal_id>", methods=["PUT", "DELETE"])
    def midline_journal_item(journal_id):
        from models import SessionLocal
        db = SessionLocal()
        try:
            if request.method == "DELETE":
                db.execute("DELETE FROM trade_journal WHERE id = ?", (journal_id,))
                db.commit()
                return jsonify({"message": f"已删除 {journal_id}"})

            if request.method == "PUT":
                data = request.get_json() or {}
                updates = []
                params = []
                for field in ["code", "name", "direction", "entry_date", "entry_price",
                              "shares", "stop_loss", "target_price", "exit_date",
                              "exit_price", "pnl", "pnl_pct",
                              "reason_entry", "reason_exit", "notes", "tags"]:
                    if field in data:
                        updates.append(f"{field} = ?")
                        params.append(data[field])
                if updates:
                    params.append(journal_id)
                    db.execute(
                        f"UPDATE trade_journal SET {', '.join(updates)} WHERE id = ?",
                        params,
                    )
                    db.commit()
                return jsonify({"message": f"已更新 {journal_id}"})
        finally:
            db.close()

    # ═══════════════════════════════════════════
    # 交易统计
    # ═══════════════════════════════════════════

    @app.route("/api/midline/journal/stats")
    def midline_journal_stats():
        """交易统计: 胜率、盈亏比、累计盈亏、最大连胜/连败"""
        from models import SessionLocal
        db = SessionLocal()
        try:
            rows = db.execute(
                "SELECT pnl, pnl_pct, direction FROM trade_journal WHERE pnl IS NOT NULL"
            ).fetchall()

            if not rows:
                return jsonify({"data": {"total_trades": 0}})

            wins = [r for r in rows if (r["pnl"] or 0) > 0]
            losses = [r for r in rows if (r["pnl"] or 0) < 0]

            total_pnl = sum(r["pnl"] or 0 for r in rows)
            avg_win = sum(r["pnl"] for r in wins) / len(wins) if wins else 0
            avg_loss = abs(sum(r["pnl"] for r in losses) / len(losses)) if losses else 0

            # 连胜/连败
            streak = 0
            max_win_streak = 0
            max_loss_streak = 0
            for r in rows:
                pnl = r["pnl"] or 0
                if pnl > 0:
                    streak = streak + 1 if streak >= 0 else 1
                    max_win_streak = max(max_win_streak, streak)
                elif pnl < 0:
                    streak = streak - 1 if streak <= 0 else -1
                    max_loss_streak = max(max_loss_streak, abs(streak))
                else:
                    streak = 0

            return jsonify({
                "data": {
                    "total_trades": len(rows),
                    "wins": len(wins),
                    "losses": len(losses),
                    "win_rate": round(len(wins) / len(rows) * 100, 1) if rows else 0,
                    "total_pnl": round(total_pnl, 2),
                    "avg_win": round(avg_win, 2),
                    "avg_loss": round(avg_loss, 2),
                    "profit_factor": round(avg_win / avg_loss, 2) if avg_loss > 0 else 0,
                    "max_win_streak": max_win_streak,
                    "max_loss_streak": max_loss_streak,
                }
            })
        finally:
            db.close()


# ═══════════════════════════════════════════
# 内部评分函数
# ═══════════════════════════════════════════

def _get_daily_kline(code, count=120):
    """获取日K线（优先缓存，兜底 Sina API）"""
    import urllib.request
    import urllib.parse
    from models import SessionLocal, KlineCache

    db = SessionLocal()
    try:
        rows = (
            db.query(KlineCache)
            .filter(KlineCache.code == code)
            .order_by(KlineCache.date.desc())
            .limit(count)
            .all()
        )
        if rows and len(rows) >= 30:
            rows.reverse()
            return [
                {"date": r.date, "open": r.open, "high": r.high,
                 "low": r.low, "close": r.close, "volume": r.volume}
                for r in rows
            ]
    except Exception:
        pass
    finally:
        db.close()

    # 兜底：腾讯 API
    try:
        prefix = "sh" if code.startswith(("6", "9")) else "sz"
        url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={prefix}{code},day,,,{count},qfq"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        klines = data.get("data", {}).get(f"{prefix}{code}", {}).get("day", []) or \
                 data.get("data", {}).get(f"{prefix}{code}", {}).get("qfqday", [])
        result = []
        for k in klines[-count:]:
            result.append({
                "date": k[0],
                "open": float(k[1]),
                "close": float(k[2]),
                "high": float(k[3]),
                "low": float(k[4]),
                "volume": float(k[5]),
            })
        return result
    except Exception:
        return []


def _calc_ema(data, period):
    """计算 EMA"""
    if len(data) < period:
        return [None] * len(data)
    k = 2 / (period + 1)
    result = [None] * len(data)
    result[period - 1] = sum(data[:period]) / period
    for i in range(period, len(data)):
        result[i] = data[i] * k + result[i - 1] * (1 - k)
    return result


def _score_stock(code):
    """对单只股票打分 — 趋势健康度 0-100"""
    kline = _get_daily_kline(code, 120)
    if len(kline) < 60:
        return {
            "total": 0, "ma_score": 0, "macd_signal": "",
            "rsi_score": 0, "trend": "数据不足", "suggestion": "数据不足",
        }

    closes = [k["close"] for k in kline]

    # ── 均线排列 (40分) ──
    ma5 = sum(closes[-5:]) / 5
    ma20 = sum(closes[-20:]) / 20
    ma60 = sum(closes[-60:]) / 60

    if ma5 > ma20 > ma60:
        ma_score = 40
        ma_text = "多头排列"
    elif ma5 > ma20:
        ma_score = 25
        ma_text = "短期多头"
    elif ma20 > ma60:
        ma_score = 10
        ma_text = "中期偏多"
    else:
        ma_score = 0
        ma_text = "空头排列"

    # ── MACD (30分) ──
    ema12 = _calc_ema(closes, 12)
    ema26 = _calc_ema(closes, 26)
    dif = [a - b if a and b else 0 for a, b in zip(ema12, ema26)]
    dea = _calc_ema(dif, 9)
    macd = [(dif[i] - (dea[i] or 0)) * 2 for i in range(len(closes))]

    if len([x for x in macd[-20:] if x is not None and x > 0]) >= 15:
        macd_score = 30
        macd_signal = "强势多头"
    elif len([x for x in macd[-10:] if x is not None and x > 0]) >= 6:
        macd_score = 20
        macd_signal = "多头"
    elif dif[-1] > (dea[-1] or 0):
        macd_score = 10
        macd_signal = "金叉初期"
    else:
        macd_score = 0
        macd_signal = "空头/死叉"

    # ── RSI (30分) ──
    gains = [max(closes[i] - closes[i - 1], 0) for i in range(1, len(closes))]
    losses = [max(closes[i - 1] - closes[i], 0) for i in range(1, len(closes))]
    avg_gain = sum(gains[-14:]) / 14
    avg_loss = sum(losses[-14:]) / 14
    rs = avg_gain / avg_loss if avg_loss > 0 else 100
    rsi = 100 - (100 / (1 + rs))

    if 40 <= rsi <= 70:
        rsi_score = 30
        rsi_text = "健康区间"
    elif 30 <= rsi < 40:
        rsi_score = 15
        rsi_text = "偏弱"
    elif rsi > 70:
        rsi_score = 10
        rsi_text = "超买"
    else:
        rsi_score = 5
        rsi_text = "超卖"

    total = ma_score + macd_score + rsi_score

    # ── 建议 ──
    if total >= 70:
        suggestion = "🟢 趋势健康，可考虑入场"
    elif total >= 40:
        suggestion = "🟡 趋势中等，等待确认"
    else:
        suggestion = "🔴 趋势偏弱，建议观望"

    # 趋势判定
    if ma_text == "多头排列" and macd_signal in ("强势多头", "多头"):
        trend = "上升趋势"
    elif ma_text == "空头排列":
        trend = "下降趋势"
    else:
        trend = "震荡/不确定"

    return {
        "total": total,
        "ma_score": ma_score,
        "ma_text": ma_text,
        "macd_signal": macd_signal,
        "macd_score": macd_score,
        "rsi_score": rsi_score,
        "rsi_value": round(rsi, 1),
        "rsi_text": rsi_text,
        "trend": trend,
        "suggestion": suggestion,
    }
