#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
因子+ML API 路由

端点:
  GET/POST /api/factor/exposure/<code>     — 个股因子暴露
  POST /api/factor/attribution             — 因子归因分析
  POST /api/ml/predict/<code>              — ML综合预测
  POST /api/ml/direction/<code>            — 方向预测
  POST /api/ml/return/<code>               — 收益率预测
"""

from flask import jsonify, request


def register_factor_routes(app):
    """注册因子分析和ML预测API"""

    # ═══════════════════════════════════════════════════════════
    # 因子暴露
    # ═══════════════════════════════════════════════════════════

    @app.route('/api/factor/exposure/<code>', methods=['GET', 'POST'])
    def api_factor_exposure(code):
        """个股20因子暴露分析"""
        from factor_attribution import factor_exposure_report

        try:
            report = factor_exposure_report(code)
            return jsonify(report)
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/factor/exposure_text/<code>', methods=['GET'])
    def api_factor_exposure_text(code):
        """因子暴露文本 (AI prompt格式)"""
        from factor_attribution import factor_exposure_text

        try:
            text = factor_exposure_text(code)
            return jsonify({'success': True, 'data': text})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # ═══════════════════════════════════════════════════════════
    # ML预测
    # ═══════════════════════════════════════════════════════════

    @app.route('/api/ml/predict/<code>', methods=['POST'])
    def api_ml_predict(code):
        """ML综合预测 (方向+收益率)"""
        from ml_predictor import predict as ml_predict

        data = request.get_json(silent=True) or {}
        horizon = int(data.get('horizon_days', 5))

        try:
            result = ml_predict(code, horizon)
            return jsonify(result)
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/ml/direction/<code>', methods=['POST'])
    def api_ml_direction(code):
        """方向预测"""
        from ml_predictor import predict_direction

        data = request.get_json(silent=True) or {}
        horizon = int(data.get('horizon_days', 5))

        try:
            result = predict_direction(code, horizon)
            return jsonify(result)
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/ml/return/<code>', methods=['POST'])
    def api_ml_return(code):
        """收益率预测"""
        from ml_predictor import predict_return

        data = request.get_json(silent=True) or {}
        horizon = int(data.get('horizon_days', 5))

        try:
            result = predict_return(code, horizon)
            return jsonify(result)
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/ml/predict_text/<code>', methods=['GET'])
    def api_ml_predict_text(code):
        """ML预测文本 (AI prompt格式)"""
        from ml_predictor import predict_text

        horizon = int(request.args.get('horizon', 5))

        try:
            text = predict_text(code, horizon)
            return jsonify({'success': True, 'data': text})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/factor/rating_v2/<code>', methods=['GET'])
    def api_factor_rating_v2(code):
        """20因子v2评级"""
        from factor_engine import get_rating_text as get_v2

        try:
            text = get_v2(code)
            return jsonify({'success': True, 'data': text})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
