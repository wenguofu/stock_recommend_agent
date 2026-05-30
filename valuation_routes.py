#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""定量估值 API 路由"""

from flask import jsonify, request


def register_valuation_routes(app):
    """注册估值分析 API"""

    @app.route("/api/valuation/quick", methods=["POST"])
    def valuation_quick():
        """
        快速估值分析
        Body: {
          code: "002916",
          industry_growth_6m: 100,   // 半年行业利润增速(%)
          industry_growth_1y: 150,   // 一年行业利润增速(%)
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
            # Auto-fill missing fields from DB
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
                    'composite_score': result.composite_score,
                    'rating': result.rating,
                    'summary': result.summary,
                    'detail': result.detail,
                }
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
