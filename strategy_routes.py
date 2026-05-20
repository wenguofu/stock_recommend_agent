"""
策略系统API路由

注册到Flask app，提供选股、验证、评分接口
"""

from flask import jsonify, request
import importlib
import os
import sys
from datetime import datetime, date

PROJECT_DIR = os.path.dirname(__file__)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)


def register_strategy_routes(app):
    """注册策略路由到Flask应用"""

    @app.route('/api/strategy/run', methods=['GET'])
    def api_strategy_run():
        """运行选股引擎
        GET /api/strategy/run?strategy=youzi&top_n=10
        """
        strategy = request.args.get('strategy', 'all')
        top_n = int(request.args.get('top_n', 10))
        
        try:
            engine = importlib.import_module('strategy_engine')
            
            if strategy == 'all':
                result = engine.run_all_strategies(top_n=top_n)
            elif strategy in engine.STRATEGIES:
                picks = engine.screen_stocks(strategy, top_n=top_n)
                result = {
                    'strategies': {
                        strategy: {
                            'strategy_name': engine.STRATEGIES[strategy]['name'],
                            'desc': engine.STRATEGIES[strategy]['desc'],
                            'picks': picks,
                        }
                    },
                    'total_unique': len(picks),
                    'date': date.today().isoformat(),
                }
            else:
                return jsonify({'success': False, 'error': f'未知策略: {strategy}'}), 400
            
            return jsonify({'success': True, 'data': result})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/strategy/save_picks', methods=['POST'])
    def api_save_picks():
        """保存选股结果到验证系统
        POST /api/strategy/save_picks  body: {strategy_results: {...}}
        """
        try:
            data = request.json or {}
            results = data.get('strategy_results', {})
            
            validator = importlib.import_module('strategy_validator')
            validator.save_picks(results)
            
            return jsonify({'success': True, 'message': '选股记录已保存'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/strategy/validate', methods=['GET'])
    def api_validate():
        """运行验证（检查历史选股表现）
        GET /api/strategy/validate
        """
        try:
            validator = importlib.import_module('strategy_validator')
            results = validator.validate_all_strategy_picks()
            return jsonify({
                'success': True,
                'data': {
                    'validated_count': results['validated_count'],
                    'success_count': results['success_count'],
                    'fail_count': results['fail_count'],
                }
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/strategy/rankings', methods=['GET'])
    def api_rankings():
        """获取策略排名
        GET /api/strategy/rankings
        """
        try:
            validator = importlib.import_module('strategy_validator')
            rankings = validator.get_strategy_rankings()
            return jsonify({'success': True, 'data': rankings})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/strategy/report', methods=['GET'])
    def api_report():
        """生成策略评分报告
        GET /api/strategy/report
        """
        try:
            validator = importlib.import_module('strategy_validator')
            results = validator.validate_all_strategy_picks()
            report = validator.generate_scoring_report(results)
            return jsonify({'success': True, 'data': {'report': report}})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/strategy/run_and_save', methods=['GET'])
    def api_run_and_save():
        """一键：运行选股 → 保存验证 → 返回结果
        GET /api/strategy/run_and_save
        """
        try:
            engine = importlib.import_module('strategy_engine')
            validator = importlib.import_module('strategy_validator')
            
            # 1. 运行选股
            results = engine.run_all_strategies(top_n=10)
            
            # 2. 保存记录
            validator.save_picks(results)
            
            # 3. 运行验证
            v_results = validator.validate_all_strategy_picks()
            
            return jsonify({
                'success': True,
                'data': {
                    'picks': results,
                    'validation': {
                        'validated_count': v_results['validated_count'],
                        'success_count': v_results['success_count'],
                        'fail_count': v_results['fail_count'],
                    }
                }
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # ═══════════════════════════════════════════════
    # 历史回测端点
    # ═══════════════════════════════════════════════

    @app.route('/api/strategy/backtest', methods=['GET'])
    def api_strategy_backtest():
        """单策略/单股历史回测
        GET /api/strategy/backtest?code=000001&strategy=youzi&forward_days=5&start=2024-01-01&end=2024-06-01&days=720
        """
        code = request.args.get('code', '')
        strategy = request.args.get('strategy', '')
        forward_days = int(request.args.get('forward_days', 5))
        start = request.args.get('start', None)
        end = request.args.get('end', None)
        days = int(request.args.get('days', 720))
        
        if not code:
            return jsonify({'success': False, 'error': '缺少股票代码'}), 400
        
        try:
            bt = importlib.import_module('strategy_backtest')
            
            if strategy == 'all' or not strategy:
                result = bt.backtest_all_strategies(
                    code, start_date=start, end_date=end,
                    forward_days=forward_days, days=days,
                )
            else:
                result = bt.backtest_strategy(
                    code, strategy,
                    start_date=start, end_date=end,
                    forward_days=forward_days, days=days,
                )
            
            return jsonify({'success': True, 'data': result})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/strategy/backtest/report', methods=['GET'])
    def api_backtest_report():
        """生成可读的回测报告（Markdown）
        GET /api/strategy/backtest/report?code=000001&strategy=youzi
        """
        code = request.args.get('code', '')
        strategy = request.args.get('strategy', '')
        forward_days = int(request.args.get('forward_days', 5))
        start = request.args.get('start', None)
        end = request.args.get('end', None)
        days = int(request.args.get('days', 720))
        
        if not code:
            return jsonify({'success': False, 'error': '缺少股票代码'}), 400
        
        try:
            bt = importlib.import_module('strategy_backtest')
            
            if strategy == 'all' or not strategy:
                result = bt.backtest_all_strategies(
                    code, start_date=start, end_date=end,
                    forward_days=forward_days, days=days,
                )
                report = bt.format_comparison_report(result)
            else:
                result = bt.backtest_strategy(
                    code, strategy,
                    start_date=start, end_date=end,
                    forward_days=forward_days, days=days,
                )
                report = bt.format_backtest_report(result)
            
            return jsonify({'success': True, 'data': {'report': report}})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/strategy/backtest/compare', methods=['GET'])
    def api_backtest_compare():
        """多策略回测对比
        GET /api/strategy/backtest/compare?code=000001&start=2024-01-01&end=2024-06-01
        """
        code = request.args.get('code', '')
        start = request.args.get('start', None)
        end = request.args.get('end', None)
        forward_days = int(request.args.get('forward_days', 5))
        days = int(request.args.get('days', 720))
        
        if not code:
            return jsonify({'success': False, 'error': '缺少股票代码'}), 400
        
        try:
            bt = importlib.import_module('strategy_backtest')
            result = bt.backtest_all_strategies(
                code, start_date=start, end_date=end,
                forward_days=forward_days, days=days,
            )
            return jsonify({'success': True, 'data': result})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/strategy/backtest/optimize', methods=['GET'])
    def api_backtest_optimize():
        """策略参数优化（网格搜索min_score）
        GET /api/strategy/backtest/optimize?code=000001&strategy=youzi&param_values=15,20,25,30,35
        """
        code = request.args.get('code', '')
        strategy = request.args.get('strategy', '')
        param_name = request.args.get('param', 'min_score')
        param_values_str = request.args.get('param_values', '10,15,20,25,30,35,40,45,50')
        forward_days = int(request.args.get('forward_days', 5))
        days = int(request.args.get('days', 720))
        metric = request.args.get('metric', 'win_rate')
        
        if not code or not strategy:
            return jsonify({'success': False, 'error': '缺少股票代码或策略名'}), 400
        
        try:
            param_values = [int(x) for x in param_values_str.split(',')]
            bt = importlib.import_module('strategy_backtest')
            result = bt.optimize_strategy(
                code, strategy,
                param_name=param_name,
                param_values=param_values,
                forward_days=forward_days,
                days=days,
                metric=metric,
            )
            return jsonify({'success': True, 'data': result})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/strategy/backtest/optimize_report', methods=['GET'])
    def api_backtest_optimize_report():
        """参数优化报告（Markdown）
        GET /api/strategy/backtest/optimize_report?code=000001&strategy=youzi
        """
        code = request.args.get('code', '')
        strategy = request.args.get('strategy', '')
        param_values_str = request.args.get('param_values', '10,15,20,25,30,35,40,45,50')
        forward_days = int(request.args.get('forward_days', 5))
        days = int(request.args.get('days', 720))
        metric = request.args.get('metric', 'win_rate')
        
        if not code or not strategy:
            return jsonify({'success': False, 'error': '缺少股票代码或策略名'}), 400
        
        try:
            param_values = [int(x) for x in param_values_str.split(',')]
            bt = importlib.import_module('strategy_backtest')
            result = bt.optimize_strategy(
                code, strategy,
                param_values=param_values,
                forward_days=forward_days,
                days=days,
                metric=metric,
            )
            report = bt.format_optimize_report(result)
            return jsonify({'success': True, 'data': {'report': report}})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    print("[策略路由] 已注册: run / save_picks / validate / rankings / report / run_and_save / backtest")
    return app
