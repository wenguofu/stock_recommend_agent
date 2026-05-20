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
