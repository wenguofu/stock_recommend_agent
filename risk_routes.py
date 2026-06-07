#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
风险管理 API 路由

端点:
  POST /api/risk/report           — 个股综合风险报告
  POST /api/risk/quick_summary    — 个股风险摘要文本
  POST /api/risk/position_size    — 凯利仓位计算
  POST /api/portfolio/correlation — 组合相关性矩阵
  POST /api/portfolio/optimize    — 均值-方差优化
  POST /api/portfolio/efficient_frontier — 有效前沿
  POST /api/portfolio/risk_parity — 风险平价
  POST /api/portfolio/recommend   — 组合推荐
"""

from flask import jsonify, request


def register_risk_routes(app):
    """在 Flask app 上注册风险管理 API 路由"""

    # ═══════════════════════════════════════════════════════════
    # 风险分析
    # ═══════════════════════════════════════════════════════════

    @app.route('/api/risk/report', methods=['POST'])
    def api_risk_report():
        """
        个股综合风险报告

        Body: {"code": "300679", "position": {"shares": 200, "cost": 55.51}}
        """
        from risk_management import risk_report

        data = request.get_json(silent=True) or {}
        code = data.get('code', '').strip()
        position = data.get('position')

        if not code:
            return jsonify({'error': 'code is required'}), 400

        try:
            report = risk_report(code, position)
            return jsonify({'success': True, 'data': report})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/risk/quick_summary', methods=['POST'])
    def api_risk_quick_summary():
        """
        个股风险摘要文本 (用于注入AI prompt)

        Body: {"code": "300679", "position": {"shares": 200, "cost": 55.51}}
        """
        from risk_management import quick_risk_summary

        data = request.get_json(silent=True) or {}
        code = data.get('code', '').strip()
        position = data.get('position')

        if not code:
            return jsonify({'error': 'code is required'}), 400

        try:
            summary = quick_risk_summary(code, position)
            return jsonify({'success': True, 'data': summary})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/risk/position_size', methods=['POST'])
    def api_risk_position_size():
        """
        凯利公式仓位计算

        Body: {"win_rate": 0.55, "avg_win_pct": 8.0, "avg_loss_pct": 5.0, "fractional": 0.5}
        """
        from risk_management import calc_kelly_position

        data = request.get_json(silent=True) or {}
        win_rate = float(data.get('win_rate', 0.5))
        avg_win_pct = float(data.get('avg_win_pct', 5.0))
        avg_loss_pct = float(data.get('avg_loss_pct', 5.0))
        fractional = float(data.get('fractional', 0.5))

        try:
            result = calc_kelly_position(win_rate, avg_win_pct, avg_loss_pct, fractional)
            return jsonify({'success': True, 'data': result})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # ═══════════════════════════════════════════════════════════
    # 组合分析
    # ═══════════════════════════════════════════════════════════

    @app.route('/api/portfolio/correlation', methods=['POST'])
    def api_portfolio_correlation():
        """
        组合相关性矩阵

        Body: {"codes": ["300679", "300433", "600150"], "days": 120}
        """
        from portfolio_optimizer import calc_correlation_matrix

        data = request.get_json(silent=True) or {}
        codes = data.get('codes', [])
        days = int(data.get('days', 120))

        if not codes or len(codes) < 2:
            return jsonify({'error': '至少需要2个股票代码'}), 400

        try:
            result = calc_correlation_matrix(codes, days)
            return jsonify(result)
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/portfolio/optimize', methods=['POST'])
    def api_portfolio_optimize():
        """
        均值-方差组合优化

        Body: {
            "codes": ["300679", "300433", "600150"],
            "days": 120,
            "target_return": 0.15,     // 可选, None=最小方差
            "risk_free_rate": 0.02,
            "max_weight": 0.35
        }
        """
        from portfolio_optimizer import markowitz_optimize

        data = request.get_json(silent=True) or {}
        codes = data.get('codes', [])
        days = int(data.get('days', 120))
        target_return = data.get('target_return')  # None = MVP
        risk_free_rate = float(data.get('risk_free_rate', 0.02))
        max_weight = float(data.get('max_weight', 0.35))

        if not codes or len(codes) < 2:
            return jsonify({'error': '至少需要2个股票代码'}), 400

        try:
            result = markowitz_optimize(
                codes, days,
                target_return=target_return,
                risk_free_rate=risk_free_rate,
                max_weight=max_weight,
            )
            return jsonify(result)
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/portfolio/efficient_frontier', methods=['POST'])
    def api_portfolio_efficient_frontier():
        """
        有效前沿

        Body: {"codes": ["300679", "300433", "600150"], "days": 120, "points": 20}
        """
        from portfolio_optimizer import efficient_frontier

        data = request.get_json(silent=True) or {}
        codes = data.get('codes', [])
        days = int(data.get('days', 120))
        points = int(data.get('points', 20))

        if not codes or len(codes) < 2:
            return jsonify({'error': '至少需要2个股票代码'}), 400

        try:
            result = efficient_frontier(codes, days, points=points)
            return jsonify(result)
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/portfolio/risk_parity', methods=['POST'])
    def api_portfolio_risk_parity():
        """
        风险平价

        Body: {"codes": ["300679", "300433", "600150"], "days": 120}
        """
        from portfolio_optimizer import risk_parity

        data = request.get_json(silent=True) or {}
        codes = data.get('codes', [])
        days = int(data.get('days', 120))

        if not codes or len(codes) < 2:
            return jsonify({'error': '至少需要2个股票代码'}), 400

        try:
            result = risk_parity(codes, days)
            return jsonify(result)
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/portfolio/recommend', methods=['POST'])
    def api_portfolio_recommend():
        """
        组合推荐

        Body: {
            "holdings": [{"code": "300679", "shares": 200, "cost": 55.51}],
            "candidates": ["300433", "603290"],
            "total_capital": 100000,
            "risk_profile": "moderate"
        }
        """
        from portfolio_optimizer import recommend_portfolio

        data = request.get_json(silent=True) or {}
        holdings = data.get('holdings', [])
        candidates = data.get('candidates', [])
        total_capital = float(data.get('total_capital', 0))
        risk_profile = data.get('risk_profile', 'moderate')

        if not total_capital or total_capital <= 0:
            return jsonify({'error': 'total_capital is required'}), 400

        if not holdings and not candidates:
            return jsonify({'error': '至少需要持仓或候选股'}), 400

        try:
            result = recommend_portfolio(
                holdings, candidates, total_capital,
                risk_profile=risk_profile,
            )
            return jsonify(result)
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # ── 组合风险报告 ──

    @app.route('/api/risk/portfolio_report', methods=['POST'])
    def api_portfolio_risk_report():
        """
        组合风险综合分析
        Body: {"codes": ["300679", "603290"], "weights": [0.4, 0.6]}
        """
        from risk_management import portfolio_risk_report, portfolio_risk_text

        data = request.get_json(silent=True) or {}
        codes = data.get('codes', [])
        weights = data.get('weights')

        if not codes or len(codes) < 2:
            return jsonify({'error': '至少需要2只股票'}), 400

        try:
            result = portfolio_risk_report(codes, weights)
            if 'error' not in result:
                result['summary_text'] = portfolio_risk_text(codes, weights)
            return jsonify({'success': True, 'data': result})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # ═══════════════════════════════════════════════════════════
    # 「击败庄家」新增端点
    # ═══════════════════════════════════════════════════════════

    @app.route('/api/risk/edge', methods=['POST'])
    def api_risk_edge():
        """
        期望值/优势计算

        Body (统计模式):
            {"win_rate": 0.55, "avg_win_pct": 8.0, "avg_loss_pct": 5.0}
        Body (价位模式):
            {"win_rate": 0.55, "entry_price": 50.0, "target_price": 55.0, "stop_price": 47.0}
        """
        from risk_management import calc_trade_edge

        data = request.get_json(silent=True) or {}
        win_rate = float(data.get('win_rate', 0.5))
        avg_win_pct = data.get('avg_win_pct')
        avg_loss_pct = data.get('avg_loss_pct')
        entry_price = data.get('entry_price')
        target_price = data.get('target_price')
        stop_price = data.get('stop_price')

        # 价位模式
        if entry_price and target_price and stop_price:
            avg_win_pct = float(avg_win_pct) if avg_win_pct else None
            avg_loss_pct = float(avg_loss_pct) if avg_loss_pct else None
        else:
            avg_win_pct = float(avg_win_pct) if avg_win_pct else 5.0
            avg_loss_pct = float(avg_loss_pct) if avg_loss_pct else 5.0

        try:
            result = calc_trade_edge(
                win_rate, avg_win_pct, avg_loss_pct,
                entry_price=float(entry_price) if entry_price else None,
                target_price=float(target_price) if target_price else None,
                stop_price=float(stop_price) if stop_price else None,
            )
            return jsonify({'success': True, 'data': result})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/risk/ruin', methods=['POST'])
    def api_risk_ruin():
        """
        破产风险计算

        Body:
            {"win_rate": 0.55, "avg_win_pct": 8.0, "avg_loss_pct": 5.0, "position_pct": 20}
        或:
            {"win_rate": 0.55, "avg_win_pct": 8.0, "avg_loss_pct": 5.0, "capital_units": 50}
        """
        from risk_management import calc_risk_of_ruin

        data = request.get_json(silent=True) or {}
        win_rate = float(data.get('win_rate', 0.5))
        avg_win_pct = float(data.get('avg_win_pct', 5.0))
        avg_loss_pct = float(data.get('avg_loss_pct', 5.0))
        position_pct = data.get('position_pct')
        capital_units = data.get('capital_units')

        try:
            result = calc_risk_of_ruin(
                win_rate, avg_win_pct, avg_loss_pct,
                position_pct=float(position_pct) if position_pct else None,
                capital_units=float(capital_units) if capital_units else 20.0,
            )
            return jsonify({'success': True, 'data': result})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/risk/dynamic_kelly', methods=['POST'])
    def api_risk_dynamic_kelly():
        """
        动态凯利仓位计算 (含不确定性+回撤调整)

        Body:
            {"win_rate": 0.55, "avg_win_pct": 8.0, "avg_loss_pct": 5.0,
             "sample_size": 30, "current_drawdown_pct": 5.0}
        """
        from risk_management import calc_dynamic_kelly

        data = request.get_json(silent=True) or {}
        win_rate = float(data.get('win_rate', 0.5))
        avg_win_pct = float(data.get('avg_win_pct', 5.0))
        avg_loss_pct = float(data.get('avg_loss_pct', 5.0))
        sample_size = int(data.get('sample_size', 30))
        current_drawdown_pct = float(data.get('current_drawdown_pct', 0))

        try:
            result = calc_dynamic_kelly(
                win_rate, avg_win_pct, avg_loss_pct,
                sample_size=sample_size,
                current_drawdown_pct=current_drawdown_pct,
            )
            return jsonify({'success': True, 'data': result})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/risk/multi_stop', methods=['POST'])
    def api_risk_multi_stop():
        """
        多层止损计算

        Body:
            {"code": "300679", "entry_price": 55.0, "max_loss_pct": 8.0,
             "atr_multiplier": 2.0, "trailing_pct": 5.0, "time_limit_days": 20}
        """
        from risk_management import calc_multi_tier_stop

        data = request.get_json(silent=True) or {}
        code = data.get('code', '').strip()
        entry_price = float(data.get('entry_price', 0))
        max_loss_pct = float(data.get('max_loss_pct', 8.0))
        atr_multiplier = float(data.get('atr_multiplier', 2.0))
        trailing_pct = float(data.get('trailing_pct', 5.0))
        time_limit_days = int(data.get('time_limit_days', 20))

        if not code or entry_price <= 0:
            return jsonify({'error': 'code 和 entry_price 必填'}), 400

        try:
            result = calc_multi_tier_stop(
                code, entry_price,
                max_loss_pct=max_loss_pct,
                atr_multiplier=atr_multiplier,
                trailing_pct=trailing_pct,
                time_limit_days=time_limit_days,
            )
            return jsonify({'success': True, 'data': result})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/risk/drawdown_position', methods=['POST'])
    def api_risk_drawdown_position():
        """
        回撤感知仓位调整

        Body:
            {"total_capital": 100000, "base_position_pct": 20,
             "current_drawdown_pct": 12.0}
        """
        from risk_management import calc_drawdown_aware_position

        data = request.get_json(silent=True) or {}
        total_capital = float(data.get('total_capital', 0))
        base_position_pct = float(data.get('base_position_pct', 20))
        current_drawdown_pct = float(data.get('current_drawdown_pct', 0))

        if total_capital <= 0:
            return jsonify({'error': 'total_capital 必须 > 0'}), 400

        try:
            result = calc_drawdown_aware_position(
                total_capital, base_position_pct, current_drawdown_pct,
            )
            return jsonify({'success': True, 'data': result})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/risk/beat_the_dealer', methods=['POST'])
    def api_beat_the_dealer():
        """
        「击败庄家」一站式仓位+止损 (推荐直接使用)

        Body:
            {"code": "300679", "total_capital": 100000,
             "entry_price": 55.0, "target_price": 65.0,
             "current_drawdown_pct": 0, "risk_profile": "moderate"}

        可选覆盖交易统计:
            {"code": "300679", "total_capital": 100000,
             "win_rate": 0.55, "avg_win_pct": 8.0, "avg_loss_pct": 5.0,
             "sample_size": 50}
        """
        from risk_management import beat_the_dealer_full

        data = request.get_json(silent=True) or {}
        code = data.get('code', '').strip()
        total_capital = float(data.get('total_capital', 0))

        if not code or total_capital <= 0:
            return jsonify({'error': 'code 和 total_capital 必填'}), 400

        try:
            result = beat_the_dealer_full(
                code=code,
                total_capital=total_capital,
                entry_price=float(data['entry_price']) if data.get('entry_price') else None,
                target_price=float(data['target_price']) if data.get('target_price') else None,
                current_drawdown_pct=float(data.get('current_drawdown_pct', 0)),
                win_rate=float(data['win_rate']) if data.get('win_rate') else None,
                avg_win_pct=float(data['avg_win_pct']) if data.get('avg_win_pct') else None,
                avg_loss_pct=float(data['avg_loss_pct']) if data.get('avg_loss_pct') else None,
                sample_size=int(data.get('sample_size', 30)),
                risk_profile=data.get('risk_profile', 'moderate'),
            )
            return jsonify({'success': True, 'data': result})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
