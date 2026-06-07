#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sprint5: 组合优化 API 路由
包装 portfolio_optimizer.py 的核心能力
"""
import logging
import traceback
from flask import jsonify, request

logger = logging.getLogger(__name__)


def _ok(data):
    return jsonify({"success": True, **data} if isinstance(data, dict) else {"success": True, "data": data})


def _err(msg, detail=None, status=400):
    payload = {"success": False, "error": msg}
    if detail:
        payload["detail"] = detail
    return jsonify(payload), status


def register_portfolio_routes(app):
    from portfolio_optimizer import (
        calc_correlation_matrix,
        markowitz_optimize,
        efficient_frontier,
        risk_parity,
        recommend_portfolio,
    )

    @app.route("/api/portfolio/correlation", methods=["GET"])
    def portfolio_correlation():
        try:
            codes = request.args.get("codes", "").split(",")
            codes = [c.strip() for c in codes if c.strip()]
            if len(codes) < 2:
                return _err("codes 至少需要 2 个, 逗号分隔")
            days = int(request.args.get("days", 120))
            r = calc_correlation_matrix(codes, days=days)
            return _ok(r) if r.get("success") else _err(r.get("error", "failed"), status=400)
        except Exception as e:
            logger.error(f"correlation err: {e}\n{traceback.format_exc()}")
            return _err(str(e), status=500)

    @app.route("/api/portfolio/markowitz", methods=["GET", "POST"])
    def portfolio_markowitz():
        try:
            if request.method == "POST":
                body = request.get_json(silent=True) or {}
            else:
                body = request.args.to_dict()
            codes = (body.get("codes") or "").split(",") if isinstance(body.get("codes"), str) else body.get("codes") or []
            codes = [str(c).strip() for c in codes if str(c).strip()]
            if len(codes) < 2:
                return _err("codes 至少需要 2 个")
            days = int(body.get("days", 120))
            target_return = body.get("target_return")
            if target_return is not None:
                target_return = float(target_return)
            r = markowitz_optimize(codes, days=days, target_return=target_return)
            return _ok(r) if r.get("success") else _err(r.get("error", "failed"), status=400)
        except Exception as e:
            logger.error(f"markowitz err: {e}\n{traceback.format_exc()}")
            return _err(str(e), status=500)

    @app.route("/api/portfolio/efficient_frontier", methods=["GET"])
    def portfolio_frontier():
        try:
            codes = request.args.get("codes", "").split(",")
            codes = [c.strip() for c in codes if c.strip()]
            if len(codes) < 2:
                return _err("codes 至少需要 2 个")
            days = int(request.args.get("days", 120))
            points = int(request.args.get("points", 20))
            r = efficient_frontier(codes, days=days, points=points)
            return _ok(r) if r.get("success") else _err(r.get("error", "failed"), status=400)
        except Exception as e:
            logger.error(f"frontier err: {e}\n{traceback.format_exc()}")
            return _err(str(e), status=500)

    @app.route("/api/portfolio/risk_parity", methods=["GET"])
    def portfolio_risk_parity():
        try:
            codes = request.args.get("codes", "").split(",")
            codes = [c.strip() for c in codes if c.strip()]
            if len(codes) < 2:
                return _err("codes 至少需要 2 个")
            days = int(request.args.get("days", 120))
            r = risk_parity(codes, days=days)
            return _ok(r) if r.get("success") else _err(r.get("error", "failed"), status=400)
        except Exception as e:
            logger.error(f"risk_parity err: {e}\n{traceback.format_exc()}")
            return _err(str(e), status=500)

    @app.route("/api/portfolio/recommend", methods=["POST"])
    def portfolio_recommend():
        try:
            body = request.get_json(silent=True) or {}
            holdings = body.get("holdings") or []
            candidates = body.get("candidates") or []
            total_capital = float(body.get("total_capital", 100000))
            days = int(body.get("days", 120))
            max_stocks = int(body.get("max_stocks", 5))
            risk_profile = body.get("risk_profile", "moderate")
            r = recommend_portfolio(
                holdings=holdings,
                candidates=candidates,
                total_capital=total_capital,
                days=days,
                max_stocks=max_stocks,
                risk_profile=risk_profile,
            )
            return _ok(r) if r.get("success") else _err(r.get("error", "failed"), status=400)
        except Exception as e:
            logger.error(f"recommend err: {e}\n{traceback.format_exc()}")
            return _err(str(e), status=500)
