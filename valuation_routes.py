#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""定量估值 API 路由"""

from flask import jsonify, request


def register_valuation_routes(app):
    """注册估值分析 API"""

    @app.route("/api/valuation/forecast/<code>", methods=["GET"])
    def valuation_forecast(code):
        """
        预览机构预测数据 (无需启动估值, 仅读取)
        Returns:
          {has_data: bool, net_profit_*: float, eps_*: float, analyst_count, rating_label, ...}
        """
        try:
            from quant_valuation import get_institutional_forecast
            fc = get_institutional_forecast(code)
            if not fc:
                return jsonify({'success': True, 'data': {
                    'has_data': False, 'source': 'none',
                    'message': '该股票暂无机构预测数据, 可手动输入增速',
                }})
            return jsonify({'success': True, 'data': {
                'has_data': fc.get('has_data', False),
                'source': 'institutional' if fc.get('has_data') else 'none',
                'net_profit_2025a': fc['net_profit_2025a'],
                'net_profit_2026e': fc['net_profit_2026e'],
                'net_profit_2027e': fc['net_profit_2027e'],
                'eps_2026e': fc['eps_2026e'],
                'eps_2027e': fc['eps_2027e'],
                'analyst_count': fc['analyst_count'],
                'rating_label': fc['rating_label'],
                'updated_at': fc['updated_at'],
                # 隐含增速: 供前端预览
                'growth_6m_implied': (
                    round((fc['net_profit_2026e'] - fc['net_profit_2025a'])
                          / fc['net_profit_2025a'] * 100, 2)
                    if fc['net_profit_2025a'] > 0 and fc['net_profit_2026e'] > 0 else 0
                ),
                'growth_1y_implied': (
                    round((pow(fc['net_profit_2027e'] / fc['net_profit_2025a'], 0.5) - 1) * 100, 2)
                    if fc['net_profit_2025a'] > 0 and fc['net_profit_2027e'] > 0 else 0
                ),
            }})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route("/api/valuation/quick", methods=["POST"])
    def valuation_quick():
        """
        快速估值分析
        Body: {
          code: "002916",
          industry_growth_6m: 100,   // 半年行业利润增速(%) 留空则使用机构预测
          industry_growth_1y: 150,   // 一年行业利润增速(%) 留空则使用机构预测
          sector_name: "PCB"         // 板块名称(可选)
        }
        """
        data = request.get_json() or {}
        code = data.get('code', '').strip()
        if not code:
            return jsonify({'error': '请输入股票代码'}), 400

        try:
            from quant_valuation import quick_valuation
            result = quick_valuation(
                code=code,
                industry_growth_6m=float(data.get('industry_growth_6m', 0)),
                industry_growth_1y=float(data.get('industry_growth_1y', 0)),
                sector_name=data.get('sector_name', ''),
            )
            return jsonify({'success': True, 'data': result})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route("/api/valuation/detail", methods=["POST"])
    def valuation_detail():
        """
        详细估值 — 手动输入所有参数
        Body: ValuationInput 的所有字段
        """
        data = request.get_json() or {}
        code = data.get('code', '').strip()
        if not code:
            return jsonify({'error': '请输入股票代码'}), 400

        try:
            from quant_valuation import ValuationInput, calculate_valuation, auto_fill_from_db

            inp = ValuationInput(
                code=code,
                name=data.get('name', ''),
                current_price=float(data.get('current_price', 0)),
                eps_ttm=float(data.get('eps_ttm', 0)),
                pe_ttm=float(data.get('pe_ttm', 0)),
                pb=float(data.get('pb', 0)),
                roe=float(data.get('roe', 0)),
                revenue_yoy=float(data.get('revenue_yoy', 0)),
                profit_yoy=float(data.get('profit_yoy', 0)),
                gross_margin=float(data.get('gross_margin', 0)),
                debt_ratio=float(data.get('debt_ratio', 0)),
                industry_growth_6m=float(data.get('industry_growth_6m', 0)),
                industry_growth_1y=float(data.get('industry_growth_1y', 0)),
                industry_growth_2y=float(data.get('industry_growth_2y', 0)),
                sector_outlook=data.get('sector_outlook', ''),
                sector_name=data.get('sector_name', ''),
            )
            # Auto-fill missing fields from DB (含机构预测)
            inp = auto_fill_from_db(inp)
            result = calculate_valuation(inp)

            return jsonify({
                'success': True,
                'data': {
                    'code': code, 'name': inp.name,
                    'current_price': inp.current_price,
                    'current_pe': result.current_pe,
                    'peg_ratio': result.peg_ratio,
                    'peg_verdict': result.peg_verdict,
                    'forward_pe_6m': result.forward_pe_6m,
                    'forward_pe_1y': result.forward_pe_1y,
                    'forward_pe_2y': result.forward_pe_2y,
                    'fair_value_current': result.fair_value_current,
                    'fair_value_growth': result.fair_value_growth,
                    'margin_of_safety': result.margin_of_safety,
                    'dcf_value': result.dcf_value,
                    'dcf_upside': result.dcf_upside,
                    'dcf_margin': result.dcf_margin,
                    'composite_score': result.composite_score,
                    'rating': result.rating,
                    'summary': result.summary,
                    'detail': result.detail,
                    'forecast': {
                        'source': inp.forecast_source or "none",
                        'has_data': inp.forecast_source == "institutional",
                        'net_profit_2025a': inp.forecast_net_profit_2025a,
                        'net_profit_2026e': inp.forecast_net_profit_2026e,
                        'net_profit_2027e': inp.forecast_net_profit_2027e,
                        'eps_2026e': inp.forecast_eps_2026e,
                        'eps_2027e': inp.forecast_eps_2027e,
                        'analyst_count': inp.forecast_analyst_count,
                        'rating_label': inp.forecast_rating_label,
                        'updated_at': inp.forecast_updated_at,
                        'growth_6m_implied': inp.industry_growth_6m,
                        'growth_1y_implied': inp.industry_growth_1y,
                        'growth_2y_implied': inp.industry_growth_2y,
                    },
                }
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
