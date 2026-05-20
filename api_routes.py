#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""API路由模块"""

from flask import jsonify, request
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
from datetime import datetime, date, timedelta
import json
import re
from data_fetchers import get_realtime_data, get_timeline_data, get_minute_kline, get_daily_kline, get_money_flow, get_money_flow_history, get_money_flow_realtime_kline, get_fundamental_data, get_industry_comparison, get_news_from_stock, get_guba_posts
from data_formatters import format_for_ai, to_json
from technical_indicators import get_comprehensive_data_with_indicators, get_comprehensive_data
from models import get_db, SessionLocal
from db import (
    get_watchlist, add_to_watchlist, remove_from_watchlist, update_watchlist_order, update_watchlist_position,
    get_config, set_config, get_all_configs,
    get_agents, get_agent, create_agent, update_agent, delete_agent,
    get_cached_analysis, save_analysis_cache,
    create_debate_job, get_debate_job, update_debate_job, list_debate_jobs, cancel_debate_job, delete_debate_job,
    get_strategies, get_strategy, create_strategy, update_strategy, delete_strategy, apply_strategy_to_agents,
    get_paper_accounts, get_paper_account, create_paper_account, update_paper_account, delete_paper_account,
    get_paper_positions, get_paper_orders, get_paper_snapshots,
    get_etf_maps, get_etf_map, create_etf_map, delete_etf_map, search_etf_replacement,
    get_latest_financial
)
from ai_service import AIService
from strategy_routes import register_strategy_routes
from utils import is_valid_stock_code
from task_scheduler import start_scheduler, _run_single_task, get_recent_alerts
from sector_data import get_sector_names, get_sector_stocks, search_sectors, get_all_sectors_with_stocks, update_sectors_from_network, get_last_update_time
from concurrent.futures import ThreadPoolExecutor, as_completed
from paper_trading import create_order, create_snapshot, calculate_account_stats, get_account_summary, get_equity_curve
from fundamental_data import fetch_and_cache, get_fundamental_data_for_ai, get_valuation
from factor_engine import get_stock_rating, get_rating_text, calculate_factors
from signal_fusion import fuse_signals, fuse_signals_text
from grid_search import grid_search, format_grid_search_result
from batch_backtest import batch_backtest, format_batch_result

def register_routes(app):
    """注册所有API路由"""
    
    @app.route('/')
    def index():
        """首页 - 股票分析门户"""
        from flask import send_from_directory
        import os
        frontend_dir = os.path.join(os.path.dirname(__file__), 'stock_frontend', 'dist')
        return send_from_directory(frontend_dir, 'index.html')
    
    @app.route('/api/v1')
    def api_docs():
        """API文档"""
        response = jsonify({
            'message': '股票数据API服务（新浪API）',
            'version': '3.0.0',
            'endpoints': {
                '/api/sina/comprehensive/<code>': '获取股票综合数据（实时、分钟K线、分时、日K线）',
                '/api/sina/comprehensive_with_indicators/<code>': '获取股票综合数据（包含技术指标：MA/EMA/MACD/RSI/KDJ/BOLL/OBV）',
                '/api/sina/realtime/<code>': '获取实时行情数据',
                '/api/sina/timeline/<code>': '获取分时数据（每分钟）',
                '/api/sina/minute/<code>': '获取分钟K线数据，参数: ?scale=5&datalen=240',
                '/api/sina/daily/<code>': '获取日K线数据，参数: ?count=240',
                '/api/sina/money_flow/<code>': '获取今日资金流向数据',
                '/api/sina/money_flow/history/<code>': '获取历史资金流向数据（日线），参数: ?days=60',
                '/api/sina/money_flow/realtime/<code>': '获取实时资金流向分钟线数据，参数: ?klt=1&lmt=0',
                '/api/sina/fundamental/<code>': '获取基本面数据',
                '/api/sina/industry_comparison/<code>': '获取行业对比数据',
                '/api/sina/for_ai/<code>': '获取格式化的股票数据，用于AI分析',
                '/api/sina/for_ai_with_indicators/<code>': '获取格式化的股票数据（含技术指标），用于AI分析',
                '/api/sentiment/news/<code>': '获取股票相关新闻，参数: ?days=7',
                '/api/sentiment/posts/<code>': '获取股吧帖子（最新+热门），参数: ?latest=10&hot=10',
                '/api/sentiment/all/<code>': '获取完整舆情数据（新闻+帖子），参数: ?days=7&latest=10&hot=10',
                '/api/strategy/strong_stocks': '获取强势股（前两个交易日10:30前涨停，当前未涨停）',
                '/api/watchlist': '自选股管理，GET获取列表，POST添加',
                '/api/watchlist/<code>': '自选股管理，DELETE删除',
                '/api/config': '配置管理，GET获取所有配置，POST设置配置',
                '/api/config/<key>': '配置管理，GET获取单个配置，POST设置配置',
                '/api/agents': 'Agent管理，GET获取列表，POST创建',
                '/api/agents/<id>': 'Agent管理，PUT更新，DELETE删除',
                '/api/ai/analyze/<code>': 'AI分析股票，POST请求，body: {"agent_id": 1}',
                '/api/ai/debate/start/<code>': '启动多Agent辩论任务，POST请求',
                '/api/ai/debate/start_multi': '启动多选一辩论任务，POST: codes, agent_ids, decision_agent_id, analysis_rounds, debate_rounds',
                '/api/ai/debate/status/<job_id>': '查询多Agent辩论任务状态',
                '/api/ai/debate/jobs': '获取辩论任务列表，参数: ?status=active|completed|failed|canceled',
                '/api/ai/debate/stop/<job_id>': '终止辩论任务，POST请求',
                '/api/ai/debate/delete/<job_id>': '删除辩论任务，DELETE请求',
                '/api/fundamentals/<code>': '获取最新财务数据（缓存优先，自动拉取）',
                '/api/factor/rating/<code>': '获取多因子综合评级',
                '/api/factor/rating_text/<code>': '获取多因子评级文本（用于AI注入）',
                '/api/signal/fuse': '融合多源信号策略，POST: {"code":"xxx"} 或 {"codes":["xxx","yyy"]}',
                '/api/strategy/grid_search': '策略参数网格搜索，POST: {"code":"xxx","strategy_type":"ma_cross","param_grid":{...}}',
                '/api/strategy/batch_backtest': '批量回测（多股票），POST: {"codes":["xxx","yyy"],"strategy_type":"ma_cross",...}',
                '/api/health': '健康检查',
            }
        })
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response

    @app.route('/api/health')
    def health():
        """健康检查"""
        return jsonify({
            'status': 'ok',
            'timestamp': datetime.now().isoformat(),
            'service': '新浪股票API服务'
        })

    @app.route('/api/sina/comprehensive/<code>')
    def get_sina_comprehensive(code):
        """获取股票的综合数据"""
        try:
            code_str = str(code).strip()
            if not is_valid_stock_code(code_str):
                return jsonify({'error': '股票代码格式错误', 'message': '股票代码应为6位数字(A股)或1-5位字母(美股)，如 000001 或 AAPL'}), 400
            
            print(f"[API] 获取综合数据，股票代码: {code_str}")
            data = get_comprehensive_data(code_str)
            result = to_json(data)
            
            response = jsonify(result)
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 获取综合数据失败: {error_msg}")
            return jsonify({'error': '获取数据失败', 'message': error_msg}), 500

    @app.route('/api/sina/comprehensive_with_indicators/<code>')
    def get_sina_comprehensive_with_indicators(code):
        """获取股票的综合数据（包含技术指标）"""
        try:
            code_str = str(code).strip()
            if not is_valid_stock_code(code_str):
                return jsonify({'error': '股票代码格式错误', 'message': '股票代码应为6位数字(A股)或1-5位字母(美股)，如 000001 或 AAPL'}), 400
            
            print(f"[API] 获取综合数据（含技术指标），股票代码: {code_str}")
            data = get_comprehensive_data_with_indicators(code_str)
            result = to_json(data)
            
            response = jsonify(result)
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 获取综合数据失败: {error_msg}")
            return jsonify({'error': '获取数据失败', 'message': error_msg}), 500

    @app.route('/api/sina/realtime/<code>')
    def get_sina_realtime(code):
        """获取实时行情数据"""
        try:
            code_str = str(code).strip()
            # 支持sh/sz格式的代码（如sh000001用于上证指数）
            if code_str.startswith(('sh', 'sz', 'gb_', '$')):
                # 直接使用，不需要验证6位数字
                print(f"[API] 获取实时行情，股票代码: {code_str}")
                data = get_realtime_data(code_str)
            elif not is_valid_stock_code(code_str):
                return jsonify({'error': '股票代码格式错误', 'message': '股票代码应为6位数字(A股)或1-5位字母(美股)，如 000001 或 AAPL'}), 400
            else:
                print(f"[API] 获取实时行情，股票代码: {code_str}")
                data = get_realtime_data(code_str)
            
            if data is None:
                return jsonify({'error': '获取数据失败', 'message': '无法获取实时行情数据'}), 500
            
            response = jsonify(data)
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 获取实时行情失败: {error_msg}")
            return jsonify({'error': '获取数据失败', 'message': error_msg}), 500

    @app.route('/api/sina/timeline/<code>')
    def get_sina_timeline(code):
        """获取分时数据（每分钟的数据点）"""
        try:
            code_str = str(code).strip()
            if not is_valid_stock_code(code_str):
                return jsonify({'error': '股票代码格式错误', 'message': '股票代码应为6位数字(A股)或1-5位字母(美股)，如 000001 或 AAPL'}), 400
            
            print(f"[API] 获取分时数据，股票代码: {code_str}")
            df = get_timeline_data(code_str)
            
            if df is None or len(df) == 0:
                return jsonify({'code': code_str, 'data': [], 'count': 0})
            
            records = df.to_dict('records')
            for record in records:
                for key, value in record.items():
                    if pd.isna(value):
                        record[key] = None
                    elif isinstance(value, pd.Timestamp):
                        record[key] = value.strftime('%Y-%m-%d %H:%M:%S')
            
            response = jsonify({'code': code_str, 'data': records, 'count': len(records)})
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 获取分时数据失败: {error_msg}")
            return jsonify({'error': '获取数据失败', 'message': error_msg}), 500

    @app.route('/api/sina/minute/<code>')
    def get_sina_minute(code):
        """获取分钟K线数据"""
        try:
            code_str = str(code).strip()
            if not is_valid_stock_code(code_str):
                return jsonify({'error': '股票代码格式错误', 'message': '股票代码应为6位数字(A股)或1-5位字母(美股)，如 000001 或 AAPL'}), 400
            
            scale = int(request.args.get('scale', 5))
            datalen = int(request.args.get('datalen', 240))
            
            if scale not in [5, 15, 30, 60]:
                return jsonify({'error': '参数错误', 'message': 'scale参数应为 5, 15, 30, 60 之一'}), 400
            
            print(f"[API] 获取分钟K线，股票代码: {code_str}, scale: {scale}, datalen: {datalen}")
            df = get_minute_kline(code_str, scale=scale, datalen=datalen)
            
            if df is None or len(df) == 0:
                return jsonify({'code': code_str, 'scale': scale, 'data': [], 'count': 0})
            
            records = df.to_dict('records')
            for record in records:
                for key, value in record.items():
                    if pd.isna(value):
                        record[key] = None
                    elif isinstance(value, pd.Timestamp):
                        record[key] = value.strftime('%Y-%m-%d %H:%M:%S')
            
            response = jsonify({'code': code_str, 'scale': scale, 'data': records, 'count': len(records)})
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 获取分钟K线失败: {error_msg}")
            return jsonify({'error': '获取数据失败', 'message': error_msg}), 500

    @app.route('/api/sina/daily/<code>')
    def get_sina_daily(code):
        """获取日K线数据（缓存优先，当天数据从新浪补充）"""
        try:
            code_str = str(code).strip()
            if not is_valid_stock_code(code_str):
                return jsonify({'error': '股票代码格式错误', 'message': '股票代码应为6位数字(A股)或1-5位字母(美股)，如 000001 或 AAPL'}), 400
            
            count = int(request.args.get('count', 240))
            print(f"[API] 获取日K线，股票代码: {code_str}, count: {count}")
            
            from db import get_kline_cache, save_kline_cache_batch
            from models import get_db as _get_db
            from datetime import date as date_type
            
            today_str = date_type.today().strftime('%Y-%m-%d')
            records = []
            from_cache = False
            
            # 1. 从本地缓存读取
            db = next(_get_db())
            try:
                cached = get_kline_cache(db, code_str, limit=count)
                if cached and len(cached) >= 20:
                    records = []
                    for r in cached:
                        d = r.get('date', '')
                        if not d:
                            continue
                        records.append({
                            'day': d,
                            'open': r.get('open'), 'high': r.get('high'),
                            'low': r.get('low'), 'close': r.get('close'),
                            'volume': r.get('volume'), 'amount': r.get('amount'),
                        })
                    records.sort(key=lambda r: r['day'])
                    if not records:
                        print(f"[API] 缓存数据全部无效: {code_str}")
                    else:
                        records.sort(key=lambda r: r.get('day', ''))
                        from_cache = True
                        print(f"[API] 日K线命中缓存: {code_str}, {len(records)}条，最新日期: {records[-1]['day']}")
            finally:
                db.close()
            
            # 2. 判断是否需要补充当天数据
            need_today = False
            if not records:
                need_today = True  # 无缓存，需要全部拉取
            elif records[-1]['day'] < today_str:
                need_today = True  # 缓存最新日期不是今天
                print(f"[API] 缓存缺少当天数据({today_str})，将从远程补充")
            
            if need_today:
                # 从远程获取
                print(f"[API] 日K线远程获取: {code_str}")
                df = get_daily_kline(code_str, count=count)
                
                if df is not None and len(df) > 0:
                    new_records = df.to_dict('records')
                    for record in new_records:
                        for key, value in record.items():
                            if pd.isna(value):
                                record[key] = None
                            elif isinstance(value, pd.Timestamp):
                                record[key] = value.strftime('%Y-%m-%d')
                    
                    if from_cache:
                        # 合并缓存+新数据，去重
                        existing_days = {r['day'] for r in records}
                        for r in new_records:
                            day_key = r.get('day') or r.get('date')
                            if day_key and day_key not in existing_days:
                                r['day'] = day_key
                                records.append(r)
                        records.sort(key=lambda r: r.get('day', ''))
                        print(f"[API] 合并后共 {len(records)} 条")
                        
                        # 写入新数据到缓存
                        try:
                            db2 = next(_get_db())
                            try:
                                save_kline_cache_batch(db2, code_str, new_records)
                                print(f"[API] 新数据已写入缓存: {len(new_records)}条")
                            finally:
                                db2.close()
                        except Exception as ce:
                            print(f"[API] 写入缓存失败: {ce}")
                    else:
                        records = new_records
                        # 统一为 day 字段
                        for r in records:
                            if 'day' not in r and 'date' in r:
                                r['day'] = r['date']
                        records.sort(key=lambda r: r.get('day', ''))
                        # 全部写入缓存
                        try:
                            db2 = next(_get_db())
                            try:
                                save_kline_cache_batch(db2, code_str, records)
                                print(f"[API] 已全部写入缓存: {len(records)}条")
                            finally:
                                db2.close()
                        except Exception as ce:
                            print(f"[API] 写入缓存失败: {ce}")
            
            if not records:
                return jsonify({'code': code_str, 'data': [], 'count': 0})
            
            response = jsonify({'code': code_str, 'data': records, 'count': len(records), 'cached': from_cache})
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 获取日K线失败: {error_msg}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': '获取数据失败', 'message': error_msg}), 500

    @app.route('/api/sina/money_flow/<code>')
    def get_sina_money_flow(code):
        """获取今日资金流向数据"""
        try:
            code_str = str(code).strip()
            if not is_valid_stock_code(code_str):
                return jsonify({'error': '股票代码格式错误', 'message': '股票代码应为6位数字(A股)或1-5位字母(美股)，如 000001 或 AAPL'}), 400
            
            print(f"[API] 获取资金流向，股票代码: {code_str}")
            data = get_money_flow(code_str)
            
            response = jsonify(data)
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 获取资金流向失败: {error_msg}")
            return jsonify({'error': '获取数据失败', 'message': error_msg}), 500

    @app.route('/api/sina/money_flow/history/<code>')
    def get_sina_money_flow_history(code):
        """获取历史资金流向数据（日线）"""
        try:
            code_str = str(code).strip()
            if not is_valid_stock_code(code_str):
                return jsonify({'error': '股票代码格式错误', 'message': '股票代码应为6位数字(A股)或1-5位字母(美股)，如 000001 或 AAPL'}), 400
            
            days = int(request.args.get('days', 60))  # 默认60天
            
            print(f"[API] 获取历史资金流向，股票代码: {code_str}, days: {days}")
            data = get_money_flow_history(code_str, days=days)
            
            response = jsonify({
                'code': code_str,
                'days': days,
                'count': len(data),
                'data': data
            })
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 获取历史资金流向失败: {error_msg}")
            return jsonify({'error': '获取数据失败', 'message': error_msg}), 500

    @app.route('/api/sina/money_flow/realtime/<code>')
    def get_sina_money_flow_realtime(code):
        """获取实时资金流向分钟线数据"""
        try:
            code_str = str(code).strip()
            if not is_valid_stock_code(code_str):
                return jsonify({'error': '股票代码格式错误', 'message': '股票代码应为6位数字(A股)或1-5位字母(美股)，如 000001 或 AAPL'}), 400
            
            klt = int(request.args.get('klt', 1))  # 1=1分钟，5=5分钟
            lmt = int(request.args.get('lmt', 0))  # 0=获取所有数据
            
            print(f"[API] 获取实时资金流向分钟线，股票代码: {code_str}, klt: {klt}, lmt: {lmt}")
            data = get_money_flow_realtime_kline(code_str, klt=klt, lmt=lmt)
            
            response = jsonify({
                'code': code_str,
                'klt': klt,
                'count': len(data),
                'data': data
            })
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 获取实时资金流向分钟线失败: {error_msg}")
            return jsonify({'error': '获取数据失败', 'message': error_msg}), 500

    @app.route('/api/sina/fundamental/<code>')
    def get_sina_fundamental(code):
        """获取股票的基本面数据"""
        try:
            code_str = str(code).strip()
            if not is_valid_stock_code(code_str):
                return jsonify({'error': '股票代码格式错误', 'message': '股票代码应为6位数字(A股)或1-5位字母(美股)，如 000001 或 AAPL'}), 400
            
            print(f"[API] 获取基本面数据，股票代码: {code_str}")
            data = get_fundamental_data(code_str)
            
            response = jsonify(data)
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 获取基本面数据失败: {error_msg}")
            return jsonify({'error': '获取数据失败', 'message': error_msg}), 500

    @app.route('/api/sina/industry_comparison/<code>')
    def get_sina_industry_comparison(code):
        """获取股票的行业对比数据"""
        try:
            code_str = str(code).strip()
            if not is_valid_stock_code(code_str):
                return jsonify({'error': '股票代码格式错误', 'message': '股票代码应为6位数字(A股)或1-5位字母(美股)，如 000001 或 AAPL'}), 400
            
            print(f"[API] 获取行业对比数据，股票代码: {code_str}")
            data = get_industry_comparison(code_str)
            
            response = jsonify(data)
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 获取行业对比数据失败: {error_msg}")
            return jsonify({'error': '获取数据失败', 'message': error_msg}), 500

    @app.route('/api/sina/for_ai/<code>')
    def get_sina_for_ai(code):
        """获取格式化的股票数据，用于AI分析"""
        try:
            code_str = str(code).strip()
            if not is_valid_stock_code(code_str):
                return jsonify({'error': '股票代码格式错误', 'message': '股票代码应为6位数字(A股)或1-5位字母(美股)，如 000001 或 AAPL'}), 400
            
            print(f"[API] 获取AI分析数据，股票代码: {code_str}")
            data = get_comprehensive_data(code_str)
            formatted = format_for_ai(data)
            
            raw_data = {
                'realtime': data['realtime'],
                'timeline_count': len(data['timeline']) if data['timeline'] is not None else 0,
                'minute_5_count': len(data['minute_5']) if data['minute_5'] is not None else 0,
                'minute_15_count': len(data['minute_15']) if data['minute_15'] is not None else 0,
                'minute_30_count': len(data['minute_30']) if data['minute_30'] is not None else 0,
                'daily_count': len(data['daily']) if data['daily'] is not None else 0,
                'sector_info': data.get('sector_info', []),
                'money_flow': data.get('money_flow', {}),
                'fundamental': data.get('fundamental', {}),
                'industry_comparison': data.get('industry_comparison', {}),
            }
            
            response = jsonify({'code': code_str, 'formatted_text': formatted, 'raw_data': raw_data})
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 获取AI分析数据失败: {error_msg}")
            return jsonify({'error': '获取数据失败', 'message': error_msg}), 500

    @app.route('/api/sina/for_ai_with_indicators/<code>')
    def get_sina_for_ai_with_indicators(code):
        """获取格式化的股票数据（包含技术指标），用于AI分析"""
        try:
            code_str = str(code).strip()
            if not is_valid_stock_code(code_str):
                return jsonify({'error': '股票代码格式错误', 'message': '股票代码应为6位数字(A股)或1-5位字母(美股)，如 000001 或 AAPL'}), 400
            
            print(f"[API] 获取AI分析数据（含技术指标），股票代码: {code_str}")
            data = get_comprehensive_data_with_indicators(code_str)
            formatted = format_for_ai(data)
            
            raw_data = {
                'realtime': data['realtime'],
                'timeline_count': len(data['timeline']) if data['timeline'] is not None else 0,
                'minute_5_count': len(data['minute_5']) if data['minute_5'] is not None else 0,
                'minute_15_count': len(data['minute_15']) if data['minute_15'] is not None else 0,
                'minute_30_count': len(data['minute_30']) if data['minute_30'] is not None else 0,
                'daily_count': len(data['daily']) if data['daily'] is not None else 0,
                'sector_info': data.get('sector_info', []),
                'money_flow': data.get('money_flow', {}),
                'fundamental': data.get('fundamental', {}),
                'industry_comparison': data.get('industry_comparison', {}),
            }
            
            # 添加技术指标摘要
            if data['daily'] is not None and len(data['daily']) > 0:
                latest = data['daily'].iloc[-1]
                indicators_summary = {}
                
                ma_cols = [col for col in data['daily'].columns if col.startswith('MA') and not col.startswith('MACD')]
                if ma_cols:
                    indicators_summary['MA'] = {col: float(latest[col]) for col in ma_cols if pd.notna(latest[col])}
                
                if 'MACD_DIF' in data['daily'].columns and pd.notna(latest['MACD_DIF']):
                    indicators_summary['MACD'] = {
                        'DIF': float(latest['MACD_DIF']),
                        'DEA': float(latest.get('MACD_DEA', 0)) if pd.notna(latest.get('MACD_DEA')) else 0,
                        'MACD': float(latest.get('MACD', 0)) if pd.notna(latest.get('MACD')) else 0
                    }
                
                if 'RSI14' in data['daily'].columns and pd.notna(latest['RSI14']):
                    indicators_summary['RSI'] = float(latest['RSI14'])
                
                if 'KDJ_K' in data['daily'].columns and pd.notna(latest['KDJ_K']):
                    indicators_summary['KDJ'] = {
                        'K': float(latest['KDJ_K']),
                        'D': float(latest.get('KDJ_D', 0)) if pd.notna(latest.get('KDJ_D')) else 0,
                        'J': float(latest.get('KDJ_J', 0)) if pd.notna(latest.get('KDJ_J')) else 0
                    }
                
                if 'BOLL_UPPER' in data['daily'].columns and pd.notna(latest['BOLL_UPPER']):
                    indicators_summary['BOLL'] = {
                        'upper': float(latest['BOLL_UPPER']),
                        'mid': float(latest.get('BOLL_MID', 0)) if pd.notna(latest.get('BOLL_MID')) else 0,
                        'lower': float(latest.get('BOLL_LOWER', 0)) if pd.notna(latest.get('BOLL_LOWER')) else 0
                    }
                
                raw_data['indicators'] = indicators_summary
            
            response = jsonify({'code': code_str, 'formatted_text': formatted, 'raw_data': raw_data})
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 获取AI分析数据失败: {error_msg}")
            return jsonify({'error': '获取数据失败', 'message': error_msg}), 500
    
    # ==================== 舆情数据API ====================
    
    @app.route('/api/sentiment/news/<code>')
    def get_sentiment_news(code):
        """获取股票相关新闻"""
        try:
            code_str = str(code).strip()
            days = int(request.args.get('days', 7))
            
            news_list = get_news_from_stock(code_str, days=days)
            
            response = jsonify({
                'code': code_str,
                'days': days,
                'count': len(news_list),
                'news': news_list
            })
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 获取新闻失败: {error_msg}")
            return jsonify({'error': '获取新闻失败', 'message': error_msg}), 500
    
    @app.route('/api/sentiment/posts/<code>')
    def get_sentiment_posts(code):
        """获取股吧帖子（最新+热门）"""
        try:
            code_str = str(code).strip()
            latest_count = int(request.args.get('latest', 10))
            hot_count = int(request.args.get('hot', 10))
            
            posts_list = get_guba_posts(code_str, latest_count=latest_count, hot_count=hot_count)
            
            # 按类型分组
            latest_posts = [p for p in posts_list if p.get('sort_type') == 'latest']
            hot_posts = [p for p in posts_list if p.get('sort_type') == 'hot']
            
            response = jsonify({
                'code': code_str,
                'latest_count': len(latest_posts),
                'hot_count': len(hot_posts),
                'total_count': len(posts_list),
                'latest_posts': latest_posts,
                'hot_posts': hot_posts,
                'all_posts': posts_list
            })
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 获取股吧帖子失败: {error_msg}")
            return jsonify({'error': '获取股吧帖子失败', 'message': error_msg}), 500
    
    @app.route('/api/sentiment/all/<code>')
    def get_sentiment_all(code):
        """获取完整舆情数据（新闻+帖子）"""
        try:
            code_str = str(code).strip()
            days = int(request.args.get('days', 7))
            latest_count = int(request.args.get('latest', 10))
            hot_count = int(request.args.get('hot', 10))
            
            # 获取新闻
            news_list = get_news_from_stock(code_str, days=days)
            
            # 获取帖子
            posts_list = get_guba_posts(code_str, latest_count=latest_count, hot_count=hot_count)
            
            # 按类型分组
            latest_posts = [p for p in posts_list if p.get('sort_type') == 'latest']
            hot_posts = [p for p in posts_list if p.get('sort_type') == 'hot']
            
            response = jsonify({
                'code': code_str,
                'news': {
                    'count': len(news_list),
                    'days': days,
                    'list': news_list
                },
                'posts': {
                    'latest_count': len(latest_posts),
                    'hot_count': len(hot_posts),
                    'total_count': len(posts_list),
                    'latest_posts': latest_posts,
                    'hot_posts': hot_posts,
                    'all_posts': posts_list
                }
            })
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 获取舆情数据失败: {error_msg}")
            return jsonify({'error': '获取舆情数据失败', 'message': error_msg}), 500
    
    # ==================== 自选股API ====================
    
    @app.route('/api/watchlist', methods=['GET'])
    def get_watchlist_api():
        """获取自选股列表"""
        db = next(get_db())
        try:
            items = get_watchlist(db)
            return jsonify({
                'success': True,
                'data': [{'id': item.id, 'code': item.code, 'name': item.name, 
                          'cost_price': item.cost_price, 'shares': item.shares,
                          'sort_order': item.sort_order} for item in items]
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            db.close()
    
    @app.route('/api/watchlist', methods=['POST'])
    def add_watchlist_api():
        """添加自选股"""
        db = next(get_db())
        try:
            data = request.json
            code = data.get('code', '').strip()
            if not is_valid_stock_code(code):
                return jsonify({'success': False, 'error': '股票代码格式错误'}), 400
            
            name = data.get('name', '')
            cost_price = data.get('cost_price')
            shares = data.get('shares')
            if cost_price is not None:
                cost_price = float(cost_price)
            if shares is not None:
                shares = int(shares)
            item = add_to_watchlist(db, code, name, cost_price, shares)
            return jsonify({
                'success': True,
                'data': {'id': item.id, 'code': item.code, 'name': item.name,
                         'cost_price': item.cost_price, 'shares': item.shares}
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            db.close()
    
    @app.route('/api/watchlist/<code>', methods=['DELETE'])
    def remove_watchlist_api(code):
        """移除自选股"""
        db = next(get_db())
        try:
            success = remove_from_watchlist(db, code)
            return jsonify({'success': success})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            db.close()
    
    @app.route('/api/watchlist/<code>/position', methods=['PUT'])
    def update_watchlist_position_api(code):
        """更新自选股持仓信息"""
        db = next(get_db())
        try:
            data = request.json
            cost_price = data.get('cost_price')
            shares = data.get('shares')
            if cost_price is not None:
                cost_price = float(cost_price)
            if shares is not None:
                shares = int(shares)
            item = update_watchlist_position(db, code, cost_price, shares)
            if not item:
                return jsonify({'success': False, 'error': '股票不在自选列表中'}), 404
            return jsonify({
                'success': True,
                'data': {'id': item.id, 'code': item.code, 'name': item.name,
                         'cost_price': item.cost_price, 'shares': item.shares}
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            db.close()
    
    @app.route('/api/watchlist/order', methods=['POST'])
    def update_watchlist_order_api():
        """更新自选股排序"""
        db = next(get_db())
        try:
            data = request.json
            orders = data.get('orders', [])  # [{'code': '000001', 'sort_order': 0}, ...]
            update_watchlist_order(db, [(item['code'], item['sort_order']) for item in orders])
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            db.close()
    
    # ==================== 配置API ====================
    
    @app.route('/api/config', methods=['GET'])
    def get_config_api():
        """获取所有配置"""
        db = next(get_db())
        try:
            configs = get_all_configs(db)
            return jsonify({'success': True, 'data': configs})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            db.close()
    
    @app.route('/api/config/<key>', methods=['GET'])
    def get_config_key_api(key):
        """获取单个配置"""
        db = next(get_db())
        try:
            value = get_config(db, key)
            return jsonify({'success': True, 'data': {key: value}})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            db.close()
    
    @app.route('/api/config/<key>', methods=['POST'])
    def set_config_api(key):
        """设置配置"""
        db = next(get_db())
        try:
            data = request.json
            value = data.get('value', '')
            set_config(db, key, value)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            db.close()
    
    # ==================== Agent API ====================
    
    @app.route('/api/agents', methods=['GET'])
    def get_agents_api():
        """获取所有Agent"""
        db = next(get_db())
        try:
            enabled_only = request.args.get('enabled_only', 'false').lower() == 'true'
            agents = get_agents(db, enabled_only)
            return jsonify({
                'success': True,
                'data': [{
                    'id': a.id,
                    'name': a.name,
                    'type': a.type,
                    'prompt': a.prompt,
                    'enabled': a.enabled,
                    'ai_provider': a.ai_provider,
                    'model': a.model,
                    'sort_order': a.sort_order
                } for a in agents]
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            db.close()
    
    @app.route('/api/agents', methods=['POST'])
    def create_agent_api():
        """创建Agent"""
        db = next(get_db())
        try:
            data = request.json
            agent = create_agent(
                db,
                name=data.get('name'),
                type=data.get('type'),
                prompt=data.get('prompt'),
                ai_provider=data.get('ai_provider'),
                model=data.get('model'),
                enabled=data.get('enabled', True),
                sort_order=data.get('sort_order', 0)
            )
            return jsonify({'success': True, 'data': {'id': agent.id}})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            db.close()
    
    @app.route('/api/agents/<int:agent_id>', methods=['PUT'])
    def update_agent_api(agent_id):
        """更新Agent"""
        db = next(get_db())
        try:
            data = request.json
            agent = update_agent(db, agent_id, **data)
            return jsonify({'success': agent is not None, 'data': {'id': agent.id} if agent else None})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            db.close()
    
    @app.route('/api/agents/<int:agent_id>', methods=['DELETE'])
    def delete_agent_api(agent_id):
        """删除Agent"""
        db = next(get_db())
        try:
            success = delete_agent(db, agent_id)
            return jsonify({'success': success})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            db.close()
    
    # ==================== AI服务工具API ====================
    
    @app.route('/api/ai/models', methods=['GET'])
    def get_ai_models():
        """获取指定AI提供商的可用模型列表"""
        try:
            provider = request.args.get('provider')
            api_key = request.args.get('api_key')
            
            if not provider:
                return jsonify({'success': False, 'error': '缺少provider参数'}), 400
            
            if not api_key:
                # 尝试从数据库获取
                db = next(get_db())
                try:
                    api_key_key = f'{provider}_api_key'
                    api_key = get_config(db, api_key_key)
                finally:
                    db.close()
            
            if not api_key:
                return jsonify({'success': False, 'error': '未配置API Key'}), 400
            
            models = AIService.get_models(provider, api_key)
            return jsonify({
                'success': True,
                'data': models
            })
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 获取模型列表失败: {error_msg}")
            return jsonify({'success': False, 'error': error_msg}), 500
    
    @app.route('/api/ai/test', methods=['POST'])
    def test_ai_connection():
        """测试AI服务连接"""
        try:
            data = request.json
            provider = data.get('provider')
            api_key = data.get('api_key')
            model = data.get('model')
            
            if not provider or not api_key:
                return jsonify({'success': False, 'error': '缺少provider或api_key参数'}), 400
            
            result = AIService.test_connection(provider, api_key, model)
            return jsonify(result)
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 测试连接失败: {error_msg}")
            return jsonify({'success': False, 'error': error_msg}), 500

    def _serialize_job(job):
        agent_info = {}
        try:
            agent_info = json.loads(job.agent_ids) if job.agent_ids else {}
        except Exception:
            agent_info = {}
        steps = []
        try:
            steps = json.loads(job.steps) if job.steps else []
        except Exception:
            steps = []
        return {
            'job_id': job.job_id,
            'code': job.code,
            'name': job.name,
            'agent_ids': agent_info.get('agent_ids', []),
            'analysis_rounds': agent_info.get('analysis_rounds', 3),
            'debate_rounds': agent_info.get('debate_rounds', 3),
            'meta': agent_info.get('meta', {}),
            'status': job.status,
            'progress': job.progress,
            'steps': steps,
            'report_md': job.report_md or '',
            'error': job.error,
            'created_at': job.created_at.isoformat() if job.created_at else None,
            'updated_at': job.updated_at.isoformat() if job.updated_at else None,
        }

    def _update_debate_job(db: SessionLocal, job_id, **kwargs):
        if 'steps' in kwargs and isinstance(kwargs['steps'], list):
            kwargs['steps'] = json.dumps(kwargs['steps'], ensure_ascii=False)
        if 'progress_detail' in kwargs and isinstance(kwargs['progress_detail'], list):
            kwargs['progress_detail'] = json.dumps(kwargs['progress_detail'], ensure_ascii=False)
        update_debate_job(db, job_id, **kwargs)

    def _is_job_canceled(db, job_id):
        job = get_debate_job(db, job_id)
        return True if (job and job.canceled) else False

    def _truncate_steps_for_db(steps, max_content_len=200):
        """Truncate step content for efficient DB writes, keeping only first N chars per step."""
        truncated = []
        for s in steps:
            entry = dict(s)
            if isinstance(entry.get('content'), str) and len(entry['content']) > max_content_len:
                entry['content'] = entry['content'][:max_content_len] + '...'
            truncated.append(entry)
        return truncated

    def _update_progress_detail(progress_detail_list, phase, round_num, agent_name, current=0, total=0):
        """Build a progress_detail entry string and append to the list."""
        if phase == 'analysis':
            detail = f"第{round_num}轮分析：{agent_name} 正在分析（{current}/{total}）"
        elif phase == 'debate':
            detail = f"第{round_num}轮辩论：{agent_name} 正在辩论（{current}/{total}）"
        elif phase == 'operator':
            detail = "报告生成中..."
        elif phase == 'complete':
            detail = "分析完成！"
        elif phase == 'pending':
            detail = "准备中..."
        else:
            detail = phase
        progress_detail_list.append(detail)

    def _run_debate_job(job_id, code_str, agent_ids, analysis_rounds, debate_rounds, position=None):
        db = SessionLocal()
        try:
            progress_detail = []
            _update_progress_detail(progress_detail, 'pending', 0, '', 0, len(agent_ids))
            _update_debate_job(db, job_id, status='running', progress=5, progress_detail=progress_detail)

            agents = []
            for agent_id in agent_ids:
                agent = get_agent(db, agent_id)
                if not agent or not agent.enabled:
                    raise ValueError(f'Agent不存在或未启用: {agent_id}')
                agents.append(agent)

            # 构建持仓上下文（如果有）
            position_context = ""
            if position:
                shares = position.get('shares', 0)
                cost = position.get('cost', 0)
                position_context = (
                    f"\n\n## User Position Info (IMPORTANT - consider this in your analysis)\n"
                    f"The user HOLDS this stock with the following position:\n"
                    f"- Shares: {shares} 股\n"
                    f"- Cost basis: {cost} 元/股\n"
                    f"- Total cost: {cost * shares:,.2f} 元\n"
                    f"- Current P&L is calculable from current_price vs cost_basis\n"
                    f"\n"
                    f"Your analysis and recommendations MUST account for this real position.\n"
                    f"Include specific advice on whether to hold, add, or reduce based on your expertise.\n"
                )

            # 构建板块背景上下文（当日热点板块 × 持仓关联）
            sector_context = ""
            try:
                from sector_utils import get_latest_sector, format_for_debate, get_holdings_sector_context
                sd = get_latest_sector(n=1)
                if sd and sd.get("sectors"):
                    holdings_ctx = get_holdings_sector_context()
                    sector_context = format_for_debate(sd, holdings_ctx)
            except Exception as e:
                print(f"[API] 板块数据加载失败: {e}")

            # 获取股票数据
            print(f"[API] 获取股票数据（辩论）: {code_str}")
            stock_data = get_comprehensive_data_with_indicators(code_str)
            formatted_data = format_for_ai(stock_data)

            # 注入基本面数据（财报优先，让AI先看到财务背景）
            try:
                from fundamental_data import get_fundamental_data_for_ai
                fund_text = get_fundamental_data_for_ai(code_str, db=db)
                formatted_data = fund_text + "\n" + formatted_data
            except Exception:
                pass

            # 注入因子评分数据（量化视角）
            try:
                from factor_engine import get_rating_text
                factor_text = get_rating_text(code_str)
                formatted_data = formatted_data + "\n" + factor_text
            except Exception:
                pass

            # 获取舆情数据（新闻+帖子）
            try:
                news_list = get_news_from_stock(code_str, days=7)[:5]
                posts_list = get_guba_posts(code_str, latest_count=5, hot_count=5)
                sentiment_text = "News:\n" + "\n".join([f"- {n.get('title','')}" for n in news_list]) + "\n\nPosts:\n" + "\n".join([f"- {p.get('title','')}" for p in posts_list[:10]])
            except Exception as e:
                sentiment_text = f"Sentiment data unavailable: {str(e)}"

            default_model_map = {
                'openai': 'gpt-3.5-turbo',
                'deepseek': 'deepseek-chat',
                'qwen': 'qwen-turbo',
                'gemini': 'gemini-pro',
                'siliconflow': 'Qwen/Qwen2.5-7B-Instruct',
                'grok': 'grok-4-0709'
            }

            def resolve_agent_config(agent):
                provider = agent.ai_provider or get_config(db, 'default_ai_provider', 'openai')
                api_key = get_config(db, f'{provider}_api_key')
                if not api_key:
                    raise ValueError(f'未配置{provider} API Key')
                model = agent.model or get_config(db, f'{provider}_model', default_model_map.get(provider, 'gpt-3.5-turbo'))
                return provider, api_key, model

            steps = []
            analysis_memory = {agent.id: [] for agent in agents}

            # 多轮分析（同一轮并行）
            for round_idx in range(1, analysis_rounds + 1):
                if _is_job_canceled(db, job_id):
                    _update_debate_job(db, job_id, status='canceled')
                    return
                # 获取当前时间（每轮分析都更新）
                current_time = datetime.now()
                current_time_str = current_time.strftime('%Y-%m-%d %H:%M:%S')
                current_time_info = f"Current Time: {current_time_str} (Weekday: {current_time.strftime('%A')})"
                
                prompts = []
                for agent in agents:
                    prev_analysis = "\n\n".join(analysis_memory[agent.id][-2:]) if analysis_memory[agent.id] else "None"
                    prompts.append((
                        agent,
                        f"{agent.prompt}\n\n"
                        f"{current_time_info}\n\n"
                        f"{sector_context}\n\n"
                        f"Stock Data:\n{formatted_data}\n\n"
                        f"Sentiment Data:\n{sentiment_text}\n\n"
                        f"{position_context}\n\n"
                        f"Round {round_idx} Analysis:\n"
                        f"Build on your previous analysis and provide new insights without repetition.\n\n"
                        f"Previous Analysis (if any):\n{prev_analysis}\n\n"
                        f"Please provide your analysis in Chinese."
                    ))

                with ThreadPoolExecutor(max_workers=min(6, len(prompts))) as executor:
                    futures = {
                        executor.submit(
                            AIService.call_agent,
                            *resolve_agent_config(agent),
                            prompt
                        ): agent
                        for agent, prompt in prompts
                    }
                    for idx, future in enumerate(as_completed(futures)):
                        agent = futures[future]
                        try:
                            result = future.result(timeout=150)
                        except Exception as e:
                            result = f"[ERROR] {agent.name} analysis failed: {str(e)}"
                        analysis_memory[agent.id].append(result)
                        steps.append({
                            'phase': 'analysis',
                            'round': round_idx,
                            'agent_id': agent.id,
                            'agent_name': agent.name,
                            'content': result,
                            'timestamp': datetime.now().isoformat()
                        })
                        progress = 20 + (round_idx - 1) * (70 // max(analysis_rounds, 1))
                        _update_progress_detail(progress_detail, 'analysis', round_idx, agent.name, idx + 1, len(prompts))
                        _update_debate_job(db, job_id, steps=_truncate_steps_for_db(steps), progress=progress, progress_detail=progress_detail)

            # 多轮辩论（同一轮并行）
            debate_history = []
            for round_idx in range(1, debate_rounds + 1):
                if _is_job_canceled(db, job_id):
                    _update_debate_job(db, job_id, status='canceled')
                    return
                # 获取当前时间（每轮辩论都更新）
                current_time = datetime.now()
                current_time_str = current_time.strftime('%Y-%m-%d %H:%M:%S')
                current_time_info = f"Current Time: {current_time_str} (Weekday: {current_time.strftime('%A')})"
                
                prompts = []
                other_latest = "\n\n".join([
                    f"{a.name}:\n{analysis_memory[a.id][-1]}"
                    for a in agents if analysis_memory[a.id]
                ])
                recent_debate = "\n\n".join([
                    f"Round {item['round']} - {item['agent_name']}:\n{item['content']}"
                    for item in debate_history[-min(len(debate_history), len(agents) * 2):]
                ]) if debate_history else "None"

                for agent in agents:
                    prompts.append((
                        agent,
                        f"{agent.prompt}\n\n"
                        f"{current_time_info}\n\n"
                        f"{sector_context}\n\n"
                        "You are participating in a multi-agent debate.\n\n"
                        f"Debate Round {round_idx}:\n"
                        "Respond with counterarguments, supporting evidence, and actionable insights.\n"
                        "Focus on your unique perspective and address opposing viewpoints.\n\n"
                        f"Other agents' latest analyses:\n{other_latest}\n\n"
                        f"Recent Debate History:\n{recent_debate}\n\n"
                        f"{position_context}\n\n"
                        "Please provide your debate response in Chinese."
                    ))

                with ThreadPoolExecutor(max_workers=min(6, len(prompts))) as executor:
                    futures = {
                        executor.submit(
                            AIService.call_agent,
                            *resolve_agent_config(agent),
                            prompt
                        ): agent
                        for agent, prompt in prompts
                    }
                    for idx, future in enumerate(as_completed(futures)):
                        agent = futures[future]
                        try:
                            result = future.result(timeout=150)
                        except Exception as e:
                            result = f"[ERROR] {agent.name} debate failed: {str(e)}"
                        item = {
                            'phase': 'debate',
                            'round': round_idx,
                            'agent_id': agent.id,
                            'agent_name': agent.name,
                            'content': result,
                            'timestamp': datetime.now().isoformat()
                        }
                        debate_history.append(item)
                        steps.append(item)
                        progress = 60 + (round_idx - 1) * (30 // max(debate_rounds, 1))
                        _update_progress_detail(progress_detail, 'debate', round_idx, agent.name, idx + 1, len(prompts))
                        _update_debate_job(db, job_id, steps=_truncate_steps_for_db(steps), progress=progress, progress_detail=progress_detail)

            # 资深操作员记录与最终报告
            operator_provider = get_config(db, 'default_ai_provider', 'openai')
            operator_api_key = get_config(db, f'{operator_provider}_api_key')
            if not operator_api_key:
                raise ValueError(f'未配置{operator_provider} API Key')
            operator_model = get_config(db, f'{operator_provider}_model', default_model_map.get(operator_provider, 'gpt-3.5-turbo'))

            transcript = "\n\n".join([
                f"[{item['phase']} R{item['round']}] {item['agent_name']}:\n{item['content']}"
                for item in steps
            ])

            operator_prompt = (
                "You are a senior trading operator and debate recorder.\n"
                "Based on the multi-agent analysis and debate transcript, produce a final research report in Markdown.\n"
                "The report must include sections: Basic Info, Overview, Key Points by Agent (ALL 12 agents must appear in table), Debate Summary, Risks, Final Recommendation.\n"
                "Use tables and bullet points where appropriate for readability.\n"
                f"\n## Sector Context\n{sector_context}\n\n\n"
                "Provide a clear trading operation suggestion in the Final Recommendation section.\\n\n"
                "CRITICAL - Sentiment & Sentient Trading Considerations:\n"
                "1. The analysis includes a 游资情绪Agent (sentient trader) who assesses market fear/greed cycles. Take this agent's perspective SERIOUSLY — it counters the conservative bias of technical/fundamental agents.\n"
                "2. If 游资情绪Agent identifies the stock in sentiment phase (b) Skepticism or (c) Gradual Conviction, lean BULLISH even if other agents say 'overbought'.\n"
                "3. If 游资情绪Agent identifies phase (d) FOMO, advocate for 'hold with trailing stop' rather than 'sell'.\n"
                "4. Only if 游资情绪Agent identifies phase (e) Exhaustion AND technical agents confirm danger signals should the report recommend 'full exit'.\n"
                "5. Your final recommendation should be GRADUAL with clear price targets and stop levels — not binary buy/sell. When in doubt between bullish sentient and bearish technical views, split the difference: reduce but don't clear.\\n\n"
                "IMPORTANT: Include a section called '## 目标价与操作时间线' with this exact table format:\n"
                "| 时间节点 | 目标价 | 操作建议 | 逻辑 |\n"
                "|---------|--------|---------|------|\n"
                "| 1周内 | xx.xx | 加仓/持仓/减仓/止盈/止损 | 短期走势研判 |\n"
                "| 1个月 | xx.xx | 加仓/持仓/减仓/止盈/止损 | 简要理由 |\n"
                "| 3个月 | xx.xx | 加仓/持仓/减仓/止盈/止损 | 简要理由 |\n"
                "| 6个月 | xx.xx | 加仓/持仓/减仓/止盈/止损 | 简要理由 |\n"
                "| 1年 | xx.xx | 加仓/持仓/减仓/止盈/止损 | 长期展望 |\n"
                "Prices must be numerical (e.g. 35.50), not percentages.\n"
                "AFTER the 目标价与操作时间线 section, add a section called '## 安全买入区间' with this table format:\n"
                "| 买入场景 | 价格区间 | 条件 | 仓位建议 |\n"
                "|---------|---------|------|---------|\n"
                "| 激进买点 | xx.xx - xx.xx | 触发条件说明 | 仓位比例 |\n"
                "| 稳健买点 | xx.xx - xx.xx | 触发条件说明 | 仓位比例 |\n"
                "| 左侧买点 | xx.xx - xx.xx | 触发条件说明 | 仓位比例 |\n"
                "If current price is too high and no safe buy zone exists, clearly state \\\"当前价格过高，暂无安全买入区间，建议观望等待回调\\\".\n"
                "IMPORTANT: The user has an existing position in this stock. Consider this in your recommendations.\n"
                f"{position_context}\\n\n"
                f"Stock Data (key fields):\\n{formatted_data}\\n\n"
                f"Sentiment Summary:\\n{sentiment_text}\\n\n"
                f"Transcript:\\n{transcript}\\n\n"
                "Please output the report in Chinese."
            )

            try:
                _update_progress_detail(progress_detail, 'operator', 0, '')
                _update_debate_job(db, job_id, steps=_truncate_steps_for_db(steps), progress_detail=progress_detail)
                report_md = AIService.call_agent(operator_provider, operator_api_key, operator_model, operator_prompt)
                _update_progress_detail(progress_detail, 'complete', 0, '')
                _update_debate_job(db, job_id, status='completed', progress=100, report_md=report_md, steps=steps, progress_detail=progress_detail, error=None)
            except Exception as e:
                fallback_report = (
                    "## 报告生成失败（已提供原始记录）\n\n"
                    f"- Error: {str(e)}\n\n"
                    "### 原始辩论记录（节选）\n\n"
                    f"{transcript[:8000]}\n\n"
                    "请稍后重试生成报告。"
                )
                _update_progress_detail(progress_detail, 'complete', 0, '')
                _update_debate_job(db, job_id, status='completed', progress=100, report_md=fallback_report, steps=steps, progress_detail=progress_detail, error=None)
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 辩论分析失败: {error_msg}")
            _update_debate_job(db, job_id, status='failed', error=error_msg)
        finally:
            db.close()

    def _run_multi_select_job(job_id, codes, agent_ids, analysis_rounds, debate_rounds):
        db = SessionLocal()
        try:
            progress_detail = []
            _update_progress_detail(progress_detail, 'pending', 0, '', 0, len(agent_ids))
            _update_debate_job(db, job_id, status='running', progress=5, progress_detail=progress_detail)

            agents = []
            for agent_id in agent_ids:
                agent = get_agent(db, agent_id)
                if not agent or not agent.enabled:
                    raise ValueError(f'Agent不存在或未启用: {agent_id}')
                agents.append(agent)

            default_model_map = {
                'openai': 'gpt-3.5-turbo',
                'deepseek': 'deepseek-chat',
                'qwen': 'qwen-turbo',
                'gemini': 'gemini-pro',
                'siliconflow': 'Qwen/Qwen2.5-7B-Instruct',
                'grok': 'grok-4-0709'
            }

            # 固定裁判，不使用数据库Agent
            operator_provider = get_config(db, 'default_ai_provider', 'openai')
            operator_api_key = get_config(db, f'{operator_provider}_api_key')
            if not operator_api_key:
                raise ValueError(f'未配置{operator_provider} API Key')
            operator_model = get_config(db, f'{operator_provider}_model', default_model_map.get(operator_provider, 'gpt-3.5-turbo'))

            # 获取多股票数据
            stock_blocks = []
            for code_str in codes:
                try:
                    stock_data = get_comprehensive_data_with_indicators(code_str)
                    formatted = format_for_ai(stock_data)
                    stock_name = ''
                    try:
                        stock_name = stock_data.get('realtime', {}).get('name', '')
                    except Exception:
                        stock_name = ''
                    stock_blocks.append(f"Stock {code_str} {stock_name}:\n{formatted}")
                except Exception as e:
                    stock_blocks.append(f"Stock {code_str}:\nData unavailable: {str(e)}")

            combined_data = "\n\n".join(stock_blocks)

            # 构建板块背景上下文
            sector_context = ""
            try:
                from sector_utils import get_latest_sector, format_for_debate
                sd = get_latest_sector(n=1)
                if sd and sd.get("sectors"):
                    sector_context = format_for_debate(sd)
            except Exception as e:
                print(f"[API] 多选板块数据加载失败: {e}")

            multi_instruction = (
                "You must choose exactly ONE stock to invest in from the list below. "
                "A capital MUST be allocated to one of these stocks. "
                "Provide your preferred choice and reasoning from your unique perspective."
            )

            def resolve_agent_config(agent):
                provider = agent.ai_provider or get_config(db, 'default_ai_provider', 'openai')
                api_key = get_config(db, f'{provider}_api_key')
                if not api_key:
                    raise ValueError(f'未配置{provider} API Key')
                model = agent.model or get_config(db, f'{provider}_model', default_model_map.get(provider, 'gpt-3.5-turbo'))
                return provider, api_key, model

            steps = []
            analysis_memory = {agent.id: [] for agent in agents}

            # 多轮分析
            for round_idx in range(1, analysis_rounds + 1):
                if _is_job_canceled(db, job_id):
                    _update_debate_job(db, job_id, status='canceled')
                    return
                # 获取当前时间（每轮分析都更新）
                current_time = datetime.now()
                current_time_str = current_time.strftime('%Y-%m-%d %H:%M:%S')
                current_time_info = f"Current Time: {current_time_str} (Weekday: {current_time.strftime('%A')})"
                
                prompts = []
                for agent in agents:
                    prev_analysis = "\n\n".join(analysis_memory[agent.id][-2:]) if analysis_memory[agent.id] else "None"
                    prompts.append((
                        agent,
                        f"{agent.prompt}\n\n"
                        f"{current_time_info}\n\n"
                        f"{sector_context}\n\n"
                        "Multi-Stock Selection Task:\n"
                        f"{combined_data}\n\n"
                        f"{multi_instruction}\n\n"
                        f"Round {round_idx} Analysis:\n"
                        "Provide new insights and clearly state your preferred stock.\n\n"
                        f"Previous Analysis (if any):\n{prev_analysis}\n\n"
                        "Please provide your analysis in Chinese."
                    ))

                with ThreadPoolExecutor(max_workers=min(6, len(prompts))) as executor:
                    futures = {
                        executor.submit(
                            AIService.call_agent,
                            *resolve_agent_config(agent),
                            prompt
                        ): agent
                        for agent, prompt in prompts
                    }
                    for idx, future in enumerate(as_completed(futures)):
                        agent = futures[future]
                        try:
                            result = future.result(timeout=150)
                        except Exception as e:
                            result = f"[ERROR] {agent.name} analysis failed: {str(e)}"
                        analysis_memory[agent.id].append(result)
                        steps.append({
                            'phase': 'analysis',
                            'round': round_idx,
                            'agent_id': agent.id,
                            'agent_name': agent.name,
                            'content': result,
                            'timestamp': datetime.now().isoformat()
                        })
                        progress = 20 + (round_idx - 1) * (70 // max(analysis_rounds, 1))
                        _update_progress_detail(progress_detail, 'analysis', round_idx, agent.name, idx + 1, len(prompts))
                        _update_debate_job(db, job_id, steps=_truncate_steps_for_db(steps), progress=progress, progress_detail=progress_detail)

            # 多轮辩论
            debate_history = []
            for round_idx in range(1, debate_rounds + 1):
                if _is_job_canceled(db, job_id):
                    _update_debate_job(db, job_id, status='canceled')
                    return
                # 获取当前时间（每轮辩论都更新）
                current_time = datetime.now()
                current_time_str = current_time.strftime('%Y-%m-%d %H:%M:%S')
                current_time_info = f"Current Time: {current_time_str} (Weekday: {current_time.strftime('%A')})"
                
                prompts = []
                other_latest = "\n\n".join([
                    f"{a.name}:\n{analysis_memory[a.id][-1]}"
                    for a in agents if analysis_memory[a.id]
                ])
                recent_debate = "\n\n".join([
                    f"Round {item['round']} - {item['agent_name']}:\n{item['content']}"
                    for item in debate_history[-min(len(debate_history), len(agents) * 2):]
                ]) if debate_history else "None"

                for agent in agents:
                    prompts.append((
                        agent,
                        f"{agent.prompt}\n\n"
                        f"{current_time_info}\n\n"
                        "You are participating in a multi-agent debate for a multi-stock selection task.\n"
                        f"{multi_instruction}\n\n"
                        f"Debate Round {round_idx}:\n"
                        "Respond with counterarguments and emphasize your preferred stock.\n\n"
                        f"Other agents' latest analyses:\n{other_latest}\n\n"
                        f"Recent Debate History:\n{recent_debate}\n\n"
                        "Please provide your debate response in Chinese."
                    ))

                with ThreadPoolExecutor(max_workers=min(6, len(prompts))) as executor:
                    futures = {
                        executor.submit(
                            AIService.call_agent,
                            *resolve_agent_config(agent),
                            prompt
                        ): agent
                        for agent, prompt in prompts
                    }
                    for idx, future in enumerate(as_completed(futures)):
                        agent = futures[future]
                        try:
                            result = future.result(timeout=150)
                        except Exception as e:
                            result = f"[ERROR] {agent.name} debate failed: {str(e)}"
                        item = {
                            'phase': 'debate',
                            'round': round_idx,
                            'agent_id': agent.id,
                            'agent_name': agent.name,
                            'content': result,
                            'timestamp': datetime.now().isoformat()
                        }
                        debate_history.append(item)
                        steps.append(item)
                        progress = 60 + (round_idx - 1) * (30 // max(debate_rounds, 1))
                        _update_progress_detail(progress_detail, 'debate', round_idx, agent.name, idx + 1, len(prompts))
                        _update_debate_job(db, job_id, steps=_truncate_steps_for_db(steps), progress=progress, progress_detail=progress_detail)

            # 决策员最终结论
            transcript = "\n\n".join([
                f"[{item['phase']} R{item['round']}] {item['agent_name']}:\n{item['content']}"
                for item in steps
            ])

            decision_prompt = (
                "You are a decisive, ruthless senior trader and final decision maker.\n"
                "You must choose exactly ONE stock to buy from the candidates.\n"
                "Be bold, concise, and action-oriented. No hedging.\n\n"
                f"Candidates:\n{combined_data}\n\n"
                f"Debate Transcript:\n{transcript}\n\n"
                "Output a Markdown report with sections: Final Choice, Rationale, Entry Plan, Risk Control.\n"
                "Please output in Chinese."
            )

            try:
                _update_progress_detail(progress_detail, 'operator', 0, '')
                _update_debate_job(db, job_id, steps=_truncate_steps_for_db(steps), progress_detail=progress_detail)
                report_md = AIService.call_agent(operator_provider, operator_api_key, operator_model, decision_prompt)
                steps.append({
                    'phase': 'debate',
                    'round': debate_rounds + 1,
                    'agent_id': 0,
                    'agent_name': "裁判（决策）",
                    'content': report_md,
                    'timestamp': datetime.now().isoformat()
                })
                _update_progress_detail(progress_detail, 'complete', 0, '')
                _update_debate_job(db, job_id, status='completed', progress=100, report_md=report_md, steps=steps, progress_detail=progress_detail, error=None)
            except Exception as e:
                fallback_report = (
                    "## 决策生成失败（已提供原始记录）\n\n"
                    f"- Error: {str(e)}\n\n"
                    "### 原始辩论记录（节选）\n\n"
                    f"{transcript[:8000]}\n\n"
                    "请稍后重试生成决策报告。"
                )
                steps.append({
                    'phase': 'debate',
                    'round': debate_rounds + 1,
                    'agent_id': 0,
                    'agent_name': "裁判（决策）",
                    'content': fallback_report,
                    'timestamp': datetime.now().isoformat()
                })
                _update_progress_detail(progress_detail, 'complete', 0, '')
                _update_debate_job(db, job_id, status='completed', progress=100, report_md=fallback_report, steps=steps, progress_detail=progress_detail, error=None)

        except Exception as e:
            error_msg = str(e)
            print(f"[API] 多选一辩论失败: {error_msg}")
            _update_debate_job(db, job_id, status='failed', error=error_msg)
        finally:
            db.close()

    @app.route('/api/ai/debate/start/<code>', methods=['POST'])
    def start_debate_job_api(code):
        """启动多Agent辩论任务（后台执行）"""
        try:
            code_str = str(code).strip()
            if not is_valid_stock_code(code_str):
                return jsonify({'success': False, 'error': '股票代码格式错误'}), 400

            data = request.json or {}
            agent_ids = data.get('agent_ids', [])
            analysis_rounds = int(data.get('analysis_rounds', 3))
            debate_rounds = int(data.get('debate_rounds', 3))
            position = data.get('position', None)  # e.g. {"shares": 1100, "cost": 37.5837}

            if not isinstance(agent_ids, list) or len(agent_ids) < 2:
                return jsonify({'success': False, 'error': '至少需要选择2个Agent参与辩论'}), 400

            job_id = str(uuid.uuid4())
            # 生成任务名称：股票名 + 日期
            try:
                realtime = get_realtime_data(code_str)
                stock_name = realtime.get('name') if isinstance(realtime, dict) else None
            except Exception:
                stock_name = None
            job_name = f"{stock_name or code_str} {datetime.now().strftime('%Y-%m-%d')}"

            db = next(get_db())
            try:
                meta = data.get('meta', {})
                if position:
                    meta['position'] = position
                create_debate_job(db, job_id, code_str, job_name, agent_ids, analysis_rounds, debate_rounds, meta=meta)
            finally:
                db.close()

            thread = threading.Thread(
                target=_run_debate_job,
                args=(job_id, code_str, agent_ids, analysis_rounds, debate_rounds, position),
                daemon=True
            )
            thread.start()

            return jsonify({'success': True, 'data': {'job_id': job_id, 'name': job_name}})
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 启动辩论任务失败: {error_msg}")
            return jsonify({'success': False, 'error': error_msg}), 500

    @app.route('/api/ai/debate/start_multi', methods=['POST'])
    def start_multi_debate_job_api():
        """启动多选一辩论任务（后台执行）"""
        try:
            data = request.json or {}
            codes = data.get('codes', [])
            agent_ids = data.get('agent_ids', [])
            analysis_rounds = int(data.get('analysis_rounds', 2))
            debate_rounds = int(data.get('debate_rounds', 1))

            if not isinstance(codes, list) or len(codes) < 2:
                return jsonify({'success': False, 'error': '至少需要选择2只股票'}), 400
            if not isinstance(agent_ids, list) or len(agent_ids) < 2:
                return jsonify({'success': False, 'error': '至少需要选择2个Agent参与辩论'}), 400
            codes = [str(c).strip() for c in codes if str(c).strip()]
            if not all(code.isdigit() and len(code) == 6 for code in codes):
                return jsonify({'success': False, 'error': '股票代码格式错误'}), 400

            job_id = str(uuid.uuid4())
            job_name = f"多选一: {'/'.join(codes)} {datetime.now().strftime('%Y-%m-%d')}"
            job_code = ",".join(codes)

            db = next(get_db())
            try:
                create_debate_job(
                    db, job_id, job_code, job_name, agent_ids, analysis_rounds, debate_rounds,
                    meta={'mode': 'multi_select', 'codes': codes}
                )
            finally:
                db.close()

            thread = threading.Thread(
                target=_run_multi_select_job,
                args=(job_id, codes, agent_ids, analysis_rounds, debate_rounds),
                daemon=True
            )
            thread.start()

            return jsonify({'success': True, 'data': {'job_id': job_id, 'name': job_name}})
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 启动多选一辩论任务失败: {error_msg}")
            return jsonify({'success': False, 'error': error_msg}), 500

    @app.route('/api/ai/debate/status/<job_id>', methods=['GET'])
    def get_debate_job_status(job_id):
        """查询辩论任务状态"""
        db = next(get_db())
        try:
            job = get_debate_job(db, job_id)
        finally:
            db.close()
        if not job:
            return jsonify({'success': False, 'error': '任务不存在'}), 404
        return jsonify({'success': True, 'data': _serialize_job(job)})

    @app.route('/api/ai/debate/jobs', methods=['GET'])
    def list_debate_jobs_api():
        """获取辩论任务列表"""
        try:
            status = request.args.get('status')
            limit = int(request.args.get('limit', 50))
            db = next(get_db())
            try:
                jobs = list_debate_jobs(db, status=status, limit=limit)
                data = [_serialize_job(job) for job in jobs]
            finally:
                db.close()
            return jsonify({'success': True, 'data': data})
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 获取辩论任务列表失败: {error_msg}")
            return jsonify({'success': False, 'error': error_msg}), 500

    @app.route('/api/ai/debate/stop/<job_id>', methods=['POST'])
    def stop_debate_job_api(job_id):
        """终止辩论任务"""
        db = next(get_db())
        try:
            job = get_debate_job(db, job_id)
            if not job:
                return jsonify({'success': False, 'error': '任务不存在'}), 404
            if job.status in ['completed', 'failed', 'canceled']:
                return jsonify({'success': False, 'error': '任务已结束，无法终止'}), 400
            cancel_debate_job(db, job_id)
            return jsonify({'success': True})
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 终止辩论任务失败: {error_msg}")
            return jsonify({'success': False, 'error': error_msg}), 500
        finally:
            db.close()

    @app.route('/api/ai/debate/delete/<job_id>', methods=['DELETE'])
    def delete_debate_job_api(job_id):
        """删除辩论任务"""
        db = next(get_db())
        try:
            job = get_debate_job(db, job_id)
            if not job:
                return jsonify({'success': False, 'error': '任务不存在'}), 404
            if job.status in ['queued', 'running']:
                return jsonify({'success': False, 'error': '任务进行中，无法删除，请先终止'}), 400
            success = delete_debate_job(db, job_id)
            return jsonify({'success': success})
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 删除辩论任务失败: {error_msg}")
            return jsonify({'success': False, 'error': error_msg}), 500
        finally:
            db.close()
    
    @app.route('/api/ai/debate/<code>', methods=['POST'])
    def debate_stock_api(code):
        """多Agent分析+辩论（含记录与最终报告）"""
        db = next(get_db())
        try:
            code_str = str(code).strip()
            if not is_valid_stock_code(code_str):
                return jsonify({'success': False, 'error': '股票代码格式错误'}), 400

            data = request.json or {}
            agent_ids = data.get('agent_ids', [])
            analysis_rounds = int(data.get('analysis_rounds', 3))
            debate_rounds = int(data.get('debate_rounds', 3))

            if not isinstance(agent_ids, list) or len(agent_ids) < 2:
                return jsonify({'success': False, 'error': '至少需要选择2个Agent参与辩论'}), 400

            # 获取Agent配置
            agents = []
            for agent_id in agent_ids:
                agent = get_agent(db, agent_id)
                if not agent or not agent.enabled:
                    return jsonify({'success': False, 'error': f'Agent不存在或未启用: {agent_id}'}), 400
                agents.append(agent)

            # 获取股票数据
            print(f"[API] 获取股票数据（辩论）: {code_str}")
            stock_data = get_comprehensive_data_with_indicators(code_str)
            formatted_data = format_for_ai(stock_data)

            default_model_map = {
                'openai': 'gpt-3.5-turbo',
                'deepseek': 'deepseek-chat',
                'qwen': 'qwen-turbo',
                'gemini': 'gemini-pro',
                'siliconflow': 'Qwen/Qwen2.5-7B-Instruct',
                'grok': 'grok-4-0709'
            }

            def resolve_agent_config(agent):
                provider = agent.ai_provider or get_config(db, 'default_ai_provider', 'openai')
                api_key = get_config(db, f'{provider}_api_key')
                if not api_key:
                    raise ValueError(f'未配置{provider} API Key')
                model = agent.model or get_config(db, f'{provider}_model', default_model_map.get(provider, 'gpt-3.5-turbo'))
                return provider, api_key, model

            steps = []
            analysis_memory = {agent.id: [] for agent in agents}

            # 获取当前时间
            current_time = datetime.now()
            current_time_str = current_time.strftime('%Y-%m-%d %H:%M:%S')
            current_time_info = f"Current Time: {current_time_str} (Weekday: {current_time.strftime('%A')})"
            
            # 3轮分析
            for round_idx in range(1, analysis_rounds + 1):
                for agent in agents:
                    provider, api_key, model = resolve_agent_config(agent)
                    prev_analysis = "\n\n".join(analysis_memory[agent.id][-2:]) if analysis_memory[agent.id] else "None"
                    prompt = (
                        f"{agent.prompt}\n\n"
                        f"{current_time_info}\n\n"
                        f"Stock Data:\n{formatted_data}\n\n"
                        f"Round {round_idx} Analysis:\n"
                        f"Build on your previous analysis and provide new insights without repetition.\n\n"
                        f"Previous Analysis (if any):\n{prev_analysis}\n\n"
                        f"Please provide your analysis in Chinese."
                    )
                    result = AIService.call_agent(provider, api_key, model, prompt)
                    analysis_memory[agent.id].append(result)
                    steps.append({
                        'phase': 'analysis',
                        'round': round_idx,
                        'agent_id': agent.id,
                        'agent_name': agent.name,
                        'content': result,
                        'timestamp': datetime.now().isoformat()
                    })

            # 3轮辩论
            debate_history = []
            for round_idx in range(1, debate_rounds + 1):
                # 获取当前时间（每轮辩论都更新）
                current_time = datetime.now()
                current_time_str = current_time.strftime('%Y-%m-%d %H:%M:%S')
                current_time_info = f"Current Time: {current_time_str} (Weekday: {current_time.strftime('%A')})"
                
                for agent in agents:
                    provider, api_key, model = resolve_agent_config(agent)
                    other_latest = "\n\n".join([
                        f"{a.name}:\n{analysis_memory[a.id][-1]}"
                        for a in agents if a.id != agent.id and analysis_memory[a.id]
                    ])
                    recent_debate = "\n\n".join([
                        f"Round {item['round']} - {item['agent_name']}:\n{item['content']}"
                        for item in debate_history[-min(len(debate_history), len(agents) * 2):]
                    ]) if debate_history else "None"

                    prompt = (
                        f"{agent.prompt}\n\n"
                        f"{current_time_info}\n\n"
                        f"{sector_context}\n\n"
                        "You are participating in a multi-agent debate.\n\n"
                        f"Debate Round {round_idx}:\n"
                        "Respond with counterarguments, supporting evidence, and actionable insights.\n"
                        "Focus on your unique perspective and address opposing viewpoints.\n\n"
                        f"Other agents' latest analyses:\n{other_latest}\n\n"
                        f"Recent Debate History:\n{recent_debate}\n\n"
                        "Please provide your debate response in Chinese."
                    )
                    result = AIService.call_agent(provider, api_key, model, prompt)
                    item = {
                        'phase': 'debate',
                        'round': round_idx,
                        'agent_id': agent.id,
                        'agent_name': agent.name,
                        'content': result,
                        'timestamp': datetime.now().isoformat()
                    }
                    debate_history.append(item)
                    steps.append(item)

            # 资深操作员记录与最终报告
            operator_provider = get_config(db, 'default_ai_provider', 'openai')
            operator_api_key = get_config(db, f'{operator_provider}_api_key')
            if not operator_api_key:
                return jsonify({'success': False, 'error': f'未配置{operator_provider} API Key'}), 400
            operator_model = get_config(db, f'{operator_provider}_model', default_model_map.get(operator_provider, 'gpt-3.5-turbo'))

            transcript = "\n\n".join([
                f"[{item['phase']} R{item['round']}] {item['agent_name']}:\n{item['content']}"
                for item in steps
            ])

            operator_prompt = (
                "You are a senior trading operator and debate recorder.\n"
                "Based on the multi-agent analysis and debate transcript, produce a final research report in Markdown.\n"
                "The report must include sections: Overview, Key Points by Agent (ALL 12 agents must appear in table), Debate Summary, Risks, Final Recommendation.\n"
                f"\n## Sector Context\n{sector_context}\n\n\n"
                "Provide a clear trading operation suggestion in the Final Recommendation section.\n\n"
                "AFTER the Final Recommendation section, add a section called '## 安全买入区间' with this table format:\n"
                "| 买入场景 | 价格区间 | 条件 | 仓位建议 |\n"
                "|---------|---------|------|---------|\n"
                "| 激进买点 | xx.xx - xx.xx | 触发条件说明 | 仓位比例 |\n"
                "| 稳健买点 | xx.xx - xx.xx | 触发条件说明 | 仓位比例 |\n"
                "| 左侧买点 | xx.xx - xx.xx | 触发条件说明 | 仓位比例 |\n"
                "If current price is too high and no safe buy zone exists, clearly state \"当前价格过高，暂无安全买入区间，建议观望等待回调\".\n"
                f"Transcript:\n{transcript}\n\n"
                "Please output the report in Chinese."
            )

            report_md = AIService.call_agent(operator_provider, operator_api_key, operator_model, operator_prompt)

            return jsonify({
                'success': True,
                'data': {
                    'steps': steps,
                    'report_md': report_md,
                    'analysis_rounds': analysis_rounds,
                    'debate_rounds': debate_rounds
                }
            })
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 辩论分析失败: {error_msg}")
            return jsonify({'success': False, 'error': error_msg}), 500
        finally:
            db.close()

    # ==================== AI分析API ====================
    
    @app.route('/api/ai/analyze/<code>', methods=['POST'])
    def analyze_stock_api(code):
        """使用Agent分析股票"""
        db = next(get_db())
        try:
            code_str = str(code).strip()
            if not is_valid_stock_code(code_str):
                return jsonify({'success': False, 'error': '股票代码格式错误'}), 400
            
            data = request.json
            agent_id = data.get('agent_id')
            use_cache = data.get('use_cache', True)
            
            # 获取Agent配置
            agent = get_agent(db, agent_id)
            if not agent or not agent.enabled:
                return jsonify({'success': False, 'error': 'Agent不存在或未启用'}), 400
            
            # 检查缓存
            if use_cache:
                cached = get_cached_analysis(db, code_str, agent.type, max_age_minutes=30)
                if cached:
                    return jsonify({
                        'success': True,
                        'data': cached,
                        'cached': True
                    })
            
            # 获取AI配置
            ai_provider = agent.ai_provider or get_config(db, 'default_ai_provider', 'openai')
            api_key_key = f'{ai_provider}_api_key'
            api_key = get_config(db, api_key_key)
            if not api_key:
                return jsonify({'success': False, 'error': f'未配置{ai_provider} API Key'}), 400
            
            model = agent.model or get_config(db, f'{ai_provider}_model', 'gpt-3.5-turbo')
            
            # 获取股票数据
            print(f"[API] 获取股票数据: {code_str}")
            stock_data = get_comprehensive_data_with_indicators(code_str)
            formatted_data = format_for_ai(stock_data)
            
            # 获取当前时间
            current_time = datetime.now()
            current_time_str = current_time.strftime('%Y-%m-%d %H:%M:%S')
            current_time_info = f"Current Time: {current_time_str} (Weekday: {current_time.strftime('%A')})"
            
            # 构建完整prompt
            full_prompt = f"{agent.prompt}\n\n{current_time_info}\n\nStock Data:\n{formatted_data}\n\nPlease provide your analysis in Chinese."
            
            # 调用AI
            try:
                print(f"[API] 调用AI分析: {agent.name} ({ai_provider})")
                result = AIService.call_agent(ai_provider, api_key, model, full_prompt)
                
                # 解析结果（如果是日内做T Agent，尝试提取价格建议）
                analysis_result = {
                    'analysis': result,
                    'agent_name': agent.name,
                    'agent_type': agent.type,
                    'timestamp': datetime.now().isoformat()
                }
                
                # 如果是日内做T Agent，尝试解析买入卖出价格
                if agent.type == 'intraday_t':
                    buy_price, sell_price = parse_intraday_t_prices(result)
                    if buy_price and sell_price:
                        analysis_result['recommendation'] = {
                            'buy_price': buy_price,
                            'sell_price': sell_price
                        }
                
                # 保存缓存
                if use_cache:
                    save_analysis_cache(db, code_str, agent.type, analysis_result)
                
                return jsonify({
                    'success': True,
                    'data': analysis_result,
                    'cached': False
                })
            except Exception as e:
                error_msg = str(e)
                print(f"[API] AI分析失败: {error_msg}")
                return jsonify({'success': False, 'error': f'AI分析失败: {error_msg}'}), 500
                
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 分析股票失败: {error_msg}")
            return jsonify({'success': False, 'error': error_msg}), 500
        finally:
            db.close()
    
    def parse_intraday_t_prices(text: str):
        """从文本中解析买入卖出价格（简单实现）"""
        try:
            # 尝试提取价格数字
            buy_match = re.search(r'买入[价格]?[：:]\s*(\d+\.?\d*)', text)
            sell_match = re.search(r'卖出[价格]?[：:]\s*(\d+\.?\d*)', text)
            
            buy_price = float(buy_match.group(1)) if buy_match else None
            sell_price = float(sell_match.group(1)) if sell_match else None
            
            return buy_price, sell_price
        except:
            return None, None
    
    # ==================== 策略API ====================
    
    @app.route('/api/strategy/strong_stocks')
    def get_strong_stocks():
        """获取强势股（前两个交易日指定时间前涨停，当前未涨停）"""
        try:
            # 获取参数：涨停截止时间，默认11:30
            limit_time = request.args.get('limit_time', '11:30')  # 涨停截止时间（T-1和T-2共用）
            
            print(f"[API] 开始筛选强势股... 截止时间={limit_time}")
            
            # 获取最近的交易日
            def get_recent_trade_dates():
                """获取最近的交易日（使用akshare，失败时回退到跳过周末）"""
                def prev_trading_day(d, n=1):
                    """往前推n个交易日，跳过周末"""
                    for _ in range(n):
                        d -= timedelta(days=1)
                        while d.weekday() >= 5:  # 5=Sat, 6=Sun
                            d -= timedelta(days=1)
                    return d
                
                try:
                    import akshare as ak
                    # 使用akshare获取交易日历
                    trade_cal = ak.tool_trade_date_hist_sina()
                    today = datetime.now().date()
                    
                    # 找到最近的交易日
                    trade_dates = pd.to_datetime(trade_cal['trade_date']).dt.date.tolist()
                    trade_dates = [d for d in trade_dates if d <= today]
                    trade_dates.sort(reverse=True)
                    
                    if len(trade_dates) >= 3:
                        return [trade_dates[0], trade_dates[1], trade_dates[2]]
                    else:
                        print(f"[API] 交易日数据不足，只有 {len(trade_dates)} 个，回退到跳过周末")
                        today = date.today()
                        # 如果今天是非交易日，先回退到最近交易日
                        t = today
                        while t.weekday() >= 5:
                            t -= timedelta(days=1)
                        return [t, prev_trading_day(t, 1), prev_trading_day(t, 2)]
                except Exception as e:
                    print(f"[API] 获取交易日失败: {e}")
                    import traceback
                    print(f"[API] 错误堆栈: {traceback.format_exc()}")
                    # 返回跳过周末的估计日期
                    today = date.today()
                    t = today
                    while t.weekday() >= 5:
                        t -= timedelta(days=1)
                    return [t, prev_trading_day(t, 1), prev_trading_day(t, 2)]
            
            trade_dates = get_recent_trade_dates()
            if len(trade_dates) < 3:
                return jsonify({'error': '无法获取足够的交易日数据'}), 500
            
            t_date = trade_dates[0]
            t1_date = trade_dates[1]
            t2_date = trade_dates[2]
            
            print(f"[API] 交易日: T={t_date}, T-1={t1_date}, T-2={t2_date}")
            
            # 获取T-1和T-2的涨停数据
            def get_limit_up_stocks(date_obj):
                """获取指定日期的涨停股票（使用akshare）"""
                try:
                    import akshare as ak
                    date_str = date_obj.strftime('%Y%m%d')
                    
                    print(f"[API] 调用akshare获取涨停数据，日期: {date_str}")
                    limit_up_df = ak.stock_zt_pool_em(date=date_str)
                    
                    if limit_up_df is None or len(limit_up_df) == 0:
                        print(f"[API] 日期 {date_str} 无涨停数据")
                        return []
                    
                    print(f"[API] 日期 {date_str} 获取到 {len(limit_up_df)} 条涨停数据")
                    
                    stocks = []
                    for idx, row in limit_up_df.iterrows():
                        # 提取股票代码
                        code = None
                        for code_field in ['代码', '股票代码', 'code']:
                            if code_field in row and pd.notna(row[code_field]):
                                code_str = str(row[code_field]).strip()
                                if code_str.isdigit() and len(code_str) == 6:
                                    code = code_str
                                    break
                                elif code_str.isdigit():
                                    code = code_str.zfill(6)
                                    break
                        
                        if not code:
                            continue
                        
                        # 提取股票名称
                        name = None
                        for name_field in ['名称', '股票名称', 'name']:
                            if name_field in row and pd.notna(row[name_field]):
                                name = str(row[name_field]).strip()
                                break
                        
                        # 提取涨停时间
                        first_limit_time = None
                        for field in ['首次封板时间', '最后封板时间', '封板时间', '涨停时间', '首次涨停时间']:
                            if field in row and pd.notna(row[field]) and str(row[field]).strip():
                                first_limit_time = str(row[field]).strip()
                                if ' ' in first_limit_time:
                                    first_limit_time = first_limit_time.split(' ')[1]
                                break
                        
                        # 提取连板数和炸板次数
                        consecutive_days = 0
                        for field in ['连板数', '连板']:
                            if field in row and pd.notna(row[field]):
                                try:
                                    consecutive_days = int(row[field])
                                except:
                                    pass
                                break
                        
                        break_count = 0
                        for field in ['炸板次数', '炸板']:
                            if field in row and pd.notna(row[field]):
                                try:
                                    break_count = int(row[field])
                                except:
                                    pass
                                break
                        
                        # 提取行业
                        industry = ''
                        for field in ['所属行业', '行业']:
                            if field in row and pd.notna(row[field]):
                                industry = str(row[field]).strip()
                                break
                        
                        stocks.append({
                            'code': code,
                            'name': name or '未知',
                            'first_limit_time': first_limit_time,
                            'consecutive_days': consecutive_days,
                            'break_count': break_count,
                            'industry': industry,
                            'date': date_str
                        })
                    
                    return stocks
                except Exception as e:
                    print(f"[API] 获取 {date_obj} 涨停数据失败: {e}")
                    import traceback
                    print(f"[API] 错误堆栈: {traceback.format_exc()}")
                    return []
            
            print("[API] 获取T-1和T-2涨停数据...")
            t1_stocks = get_limit_up_stocks(t1_date)
            t2_stocks = get_limit_up_stocks(t2_date)
            
            print(f"[API] T-1涨停股票数: {len(t1_stocks)}, T-2涨停股票数: {len(t2_stocks)}")
            
            # 筛选指定时间之前涨停的股票
            def filter_early_limit(stocks, cutoff_time):
                """筛选指定时间之前涨停的股票"""
                result = []
                try:
                    # 将截止时间转换为数字格式（如11:30 -> 113000）
                    if ':' in cutoff_time:
                        parts = cutoff_time.split(':')
                        cutoff_value = int(parts[0]) * 10000 + int(parts[1]) * 100
                    else:
                        cutoff_value = int(cutoff_time)
                except:
                    cutoff_value = 113000  # 默认11:30
                
                print(f"[API] 筛选截止时间值: {cutoff_value}")
                
                for stock in stocks:
                    time_str = stock.get('first_limit_time', '')
                    try:
                        # 处理不同格式的时间
                        if ':' in str(time_str):
                            # 格式如 "09:25:00" 或 "09:25"
                            parts = str(time_str).split(':')
                            time_value = int(parts[0]) * 10000 + int(parts[1]) * 100
                            if len(parts) > 2:
                                time_value += int(parts[2])
                        else:
                            # 格式如 "092500" 或 92500
                            time_value = int(time_str)
                        
                        # 在截止时间之前或等于截止时间涨停
                        if time_value <= cutoff_value:
                            result.append(stock)
                    except Exception as e:
                        print(f"[API] 解析时间失败: {time_str}, 错误: {e}")
                        continue
                
                print(f"[API] 筛选前{len(stocks)}只，筛选后{len(result)}只")
                return result
            
            t1_early = filter_early_limit(t1_stocks, limit_time)
            t2_early = filter_early_limit(t2_stocks, limit_time)
            
            print(f"[API] T-1早盘涨停: {len(t1_early)}, T-2早盘涨停: {len(t2_early)}")
            
            # 找出同时在T-1和T-2都早盘涨停的股票
            t1_codes = {s['code'] for s in t1_early}
            t2_codes = {s['code'] for s in t2_early}
            common_codes = t1_codes & t2_codes
            
            print(f"[API] 同时在T-1和T-2早盘涨停的股票数: {len(common_codes)}")
            
            # 获取T日（今天）的涨停股票
            t_limit_stocks = get_limit_up_stocks(t_date)
            t_limit_codes = {s['code'] for s in t_limit_stocks}
            
            print(f"[API] T日涨停股票数: {len(t_limit_codes)}")

            # 获取T日（今天）的跌停股票 - 兼容不同版本的akshare
            t_down_codes = set()
            try:
                import akshare as ak
                # 新版akshare可能没有stock_dt_pool_em，尝试不同名称
                dt_funcs = ['stock_dt_pool_em', 'stock_zt_pool_em']
                for func_name in dt_funcs:
                    if hasattr(ak, func_name):
                        t_down_df = getattr(ak, func_name)(date=t_date.strftime('%Y%m%d'))
                        if t_down_df is not None and len(t_down_df) > 0:
                            code_col = None
                            for col in ['代码', '股票代码', 'code']:
                                if col in t_down_df.columns:
                                    code_col = col
                                    break
                            if code_col and func_name == 'stock_dt_pool_em':
                                t_down_codes = set(t_down_df[code_col].astype(str).str.zfill(6).tolist())
                            break
                print(f"[API] T日跌停股票数: {len(t_down_codes)}")
            except Exception as e:
                print(f"[API] 获取T日跌停数据失败（跳过）: {e}")
            
            # 筛选出今天还没有涨停且未跌停的股票
            result_codes = common_codes - t_limit_codes - t_down_codes
            
            print(f"[API] 符合条件的强势股数量: {len(result_codes)}")
            
            # 同时记录被过滤的股票（用于调试/展示）
            filtered_because_limitup = common_codes & t_limit_codes
            filtered_because_down = common_codes & t_down_codes
            
            if len(common_codes) > 0 and len(result_codes) == 0:
                print(f"[API] 共{len(common_codes)}只候选股，全部因今日涨跌停被过滤")
            
            # 组装结果
            result_stocks = []
            for code in result_codes:
                # 从T-1数据中获取股票信息
                t1_info = next((s for s in t1_early if s['code'] == code), None)
                t2_info = next((s for s in t2_early if s['code'] == code), None)
                
                if t1_info:
                    stock_data = {
                        'code': code,
                        'name': t1_info['name'],
                        't1_limit_time': t1_info['first_limit_time'],
                        't2_limit_time': t2_info['first_limit_time'] if t2_info else None,
                        'consecutive_days': t1_info.get('consecutive_days', 0),
                        'break_count': t1_info.get('break_count', 0),
                        'industry': t1_info.get('industry', ''),
                        'current_price': None,
                        'change_percent': None,
                        'volume': None,
                        'amount': None,
                    }
                    
                    # 获取当前实时行情
                    try:
                        realtime = get_realtime_data(code)
                        if realtime:
                            stock_data['current_price'] = realtime.get('current_price')
                            stock_data['change_percent'] = realtime.get('change_percent')
                            stock_data['volume'] = realtime.get('volume')
                            stock_data['amount'] = realtime.get('amount')
                    except Exception as e:
                        print(f"[API] 获取 {code} 实时行情失败: {e}")
                    
                    result_stocks.append(stock_data)
            
            print(f"[API] 返回强势股数据，共 {len(result_stocks)} 只")
            
            return jsonify({
                'strategy': 'strong_stocks',
                'description': f'T-1和T-2日{limit_time}前涨停，T日未涨停',
                'params': {
                    'limit_time': limit_time,
                },
                'trade_dates': {
                    'T': t_date.strftime('%Y-%m-%d'),
                    'T-1': t1_date.strftime('%Y-%m-%d'),
                    'T-2': t2_date.strftime('%Y-%m-%d'),
                },
                'count': len(result_stocks),
                'stocks': result_stocks
            })
        
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 筛选强势股失败: {error_msg}")
            import traceback
            print(f"[API] 错误堆栈: {traceback.format_exc()}")
            return jsonify({'error': '筛选强势股失败', 'message': error_msg}), 500

    # ==================== 策略库 API ====================

    @app.route('/api/strategies')
    def list_strategies():
        """获取策略列表"""
        try:
            db = SessionLocal()
            try:
                category = request.args.get('category')
                enabled_only = request.args.get('enabled_only', 'false').lower() == 'true'
                strategies = get_strategies(db, category=category, enabled_only=enabled_only)
                result = []
                for s in strategies:
                    result.append({
                        'id': s.id,
                        'name': s.name,
                        'description': s.description,
                        'category': s.category,
                        'enabled': s.enabled,
                        'sort_order': s.sort_order,
                        'created_at': s.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                        'agent_count': len(json.loads(s.agent_configs)) if s.agent_configs else 0,
                    })
                return jsonify({'strategies': result, 'count': len(result)})
            finally:
                db.close()
        except Exception as e:
            return jsonify({'error': '获取策略列表失败', 'message': str(e)}), 500

    @app.route('/api/strategies/<int:strategy_id>')
    def get_strategy_detail(strategy_id):
        """获取策略详情"""
        try:
            db = SessionLocal()
            try:
                s = get_strategy(db, strategy_id)
                if not s:
                    return jsonify({'error': '策略不存在'}), 404
                return jsonify({
                    'id': s.id,
                    'name': s.name,
                    'description': s.description,
                    'category': s.category,
                    'doc_md': s.doc_md,
                    'agent_configs': json.loads(s.agent_configs) if s.agent_configs else [],
                    'enabled': s.enabled,
                    'sort_order': s.sort_order,
                    'created_at': s.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                })
            finally:
                db.close()
        except Exception as e:
            return jsonify({'error': '获取策略详情失败', 'message': str(e)}), 500

    @app.route('/api/strategies', methods=['POST'])
    def create_strategy_api():
        """创建策略"""
        try:
            data = request.json
            if not data or not data.get('name'):
                return jsonify({'error': '策略名不能为空'}), 400
            agent_configs = data.get('agent_configs', [])
            if isinstance(agent_configs, list):
                agent_configs = json.dumps(agent_configs, ensure_ascii=False)
            db = SessionLocal()
            try:
                s = create_strategy(
                    db,
                    name=data['name'],
                    description=data.get('description'),
                    category=data.get('category'),
                    doc_md=data.get('doc_md'),
                    agent_configs=agent_configs,
                    sort_order=data.get('sort_order', 0)
                )
                return jsonify({
                    'id': s.id,
                    'name': s.name,
                    'message': '策略创建成功'
                }), 201
            finally:
                db.close()
        except Exception as e:
            return jsonify({'error': '创建策略失败', 'message': str(e)}), 500

    @app.route('/api/strategies/<int:strategy_id>', methods=['PUT'])
    def update_strategy_api(strategy_id):
        """更新策略"""
        try:
            data = request.json
            db = SessionLocal()
            try:
                kwargs = {}
                for key in ['name', 'description', 'category', 'doc_md', 'enabled', 'sort_order']:
                    if key in data:
                        kwargs[key] = data[key]
                if 'agent_configs' in data:
                    configs = data['agent_configs']
                    if isinstance(configs, list):
                        configs = json.dumps(configs, ensure_ascii=False)
                    kwargs['agent_configs'] = configs
                s = update_strategy(db, strategy_id, **kwargs)
                if not s:
                    return jsonify({'error': '策略不存在'}), 404
                return jsonify({'message': '策略更新成功', 'id': s.id})
            finally:
                db.close()
        except Exception as e:
            return jsonify({'error': '更新策略失败', 'message': str(e)}), 500

    @app.route('/api/strategies/<int:strategy_id>', methods=['DELETE'])
    def delete_strategy_api(strategy_id):
        """删除策略"""
        try:
            db = SessionLocal()
            try:
                if delete_strategy(db, strategy_id):
                    return jsonify({'message': '策略已删除'})
                return jsonify({'error': '策略不存在'}), 404
            finally:
                db.close()
        except Exception as e:
            return jsonify({'error': '删除策略失败', 'message': str(e)}), 500

    @app.route('/api/strategies/<int:strategy_id>/run', methods=['POST'])
    def run_strategy_api(strategy_id):
        """运行策略：使用策略的Agent对指定股票启动辩论"""
        try:
            db = SessionLocal()
            try:
                s = get_strategy(db, strategy_id)
                if not s:
                    return jsonify({'error': '策略不存在'}), 404

                data = request.json or {}
                codes = data.get('codes', [])
                analysis_rounds = int(data.get('analysis_rounds', 2))
                debate_rounds = int(data.get('debate_rounds', 1))

                if not isinstance(codes, list) or len(codes) == 0:
                    return jsonify({'error': '请至少选择1只股票'}), 400

                # 获取策略的所有Agent ID
                configs = json.loads(s.agent_configs) if s.agent_configs else []
                agent_names = [c['name'] for c in configs]

                # 从数据库查找对应该策略的Agent
                existing_agents = get_agents(db, enabled_only=False)
                name_to_id = {a.name: a.id for a in existing_agents}

                agent_ids = []
                for name in agent_names:
                    if name in name_to_id:
                        agent_ids.append(name_to_id[name])

                if len(agent_ids) < 2:
                    # 策略的Agent未被应用，先自动应用
                    results = apply_strategy_to_agents(db, strategy_id)
                    if results:
                        # 重新获取Agent ID
                        existing_agents = get_agents(db, enabled_only=False)
                        name_to_id = {a.name: a.id for a in existing_agents}
                        agent_ids = [name_to_id[n] for n in agent_names if n in name_to_id]

                if len(agent_ids) < 2:
                    return jsonify({'error': '策略Agent不足（至少需要2个），请先应用策略'}), 400

            finally:
                db.close()

            # 按模式启动辩论
            codes = [str(c).strip() for c in codes if str(c).strip()]
            
            if len(codes) == 1:
                # 单只股票 - 使用单股票辩论
                code_str = codes[0]
                job_id = str(uuid.uuid4())
                try:
                    from data_fetchers import get_realtime_data
                    realtime = get_realtime_data(code_str)
                    stock_name = realtime.get('name') if isinstance(realtime, dict) else None
                except Exception:
                    stock_name = None
                job_name = f"{s.name} | {stock_name or code_str} {datetime.now().strftime('%Y-%m-%d')}"

                db2 = next(get_db())
                try:
                    create_debate_job(db2, job_id, code_str, job_name, agent_ids, analysis_rounds, debate_rounds,
                                      meta={'strategy_id': strategy_id, 'strategy_name': s.name})
                finally:
                    db2.close()

                thread = threading.Thread(
                    target=_run_debate_job,
                    args=(job_id, code_str, agent_ids, analysis_rounds, debate_rounds, None),
                    daemon=True
                )
                thread.start()
            else:
                # 多只股票 - 使用多选一辩论
                job_id = str(uuid.uuid4())
                job_name = f"{s.name}: {'/'.join(codes)} {datetime.now().strftime('%Y-%m-%d')}"
                job_code = ",".join(codes)

                codes_str_list = [str(c).strip() for c in codes]

                db2 = next(get_db())
                try:
                    create_debate_job(
                        db2, job_id, job_code, job_name, agent_ids, analysis_rounds, debate_rounds,
                        meta={'mode': 'multi_select', 'codes': codes_str_list, 'strategy_id': strategy_id, 'strategy_name': s.name}
                    )
                finally:
                    db2.close()

                thread = threading.Thread(
                    target=_run_multi_select_job,
                    args=(job_id, codes_str_list, agent_ids, analysis_rounds, debate_rounds),
                    daemon=True
                )
                thread.start()

            return jsonify({
                'success': True,
                'data': {
                    'job_id': job_id,
                    'name': job_name,
                    'agent_ids': agent_ids,
                    'agent_count': len(agent_ids)
                }
            })
        except Exception as e:
            error_msg = str(e)
            import traceback
            print(f"[API] 运行策略失败: {error_msg}")
            print(traceback.format_exc())
            return jsonify({'error': '运行策略失败', 'message': error_msg}), 500

    @app.route('/api/strategies/<int:strategy_id>/apply', methods=['POST'])
    def apply_strategy_api(strategy_id):
        """应用策略到Agent"""
        try:
            db = SessionLocal()
            try:
                results = apply_strategy_to_agents(db, strategy_id)
                if results is None:
                    return jsonify({'error': '策略不存在或无Agent配置'}), 404
                return jsonify({
                    'message': '策略应用成功',
                    'results': results,
                    'count': len(results)
                })
            finally:
                db.close()
        except Exception as e:
            return jsonify({'error': '应用策略失败', 'message': str(e)}), 500

    # ==================== 盯盘任务 API ====================
    
    @app.route('/api/tasks', methods=['GET'])
    def list_tasks():
        db = SessionLocal()
        try:
            from models import MonitorTask
            tasks = db.query(MonitorTask).order_by(MonitorTask.created_at.desc()).all()
            return jsonify({
                'success': True,
                'data': [{
                    'id': t.id, 'name': t.name, 'task_type': t.task_type,
                    'codes': json.loads(t.codes) if t.codes else [],
                    'schedule': t.schedule, 'enabled': t.enabled,
                    'agent_ids': json.loads(t.agent_ids) if t.agent_ids else [],
                    'config': json.loads(t.config) if t.config else {},
                    'last_run': t.last_run.isoformat() if t.last_run else None,
                    'next_run': t.next_run.isoformat() if t.next_run else None,
                    'created_at': t.created_at.isoformat(),
                } for t in tasks]
            })
        finally:
            db.close()
    
    @app.route('/api/tasks', methods=['POST'])
    def create_task():
        from models import MonitorTask
        db = SessionLocal()
        try:
            data = request.json
            task = MonitorTask(
                name=data.get('name', '未命名任务'),
                task_type=data.get('task_type', 'price_alert'),
                codes=json.dumps(data.get('codes', []), ensure_ascii=False),
                schedule=data.get('schedule', 'every_15m'),
                agent_ids=json.dumps(data.get('agent_ids', []), ensure_ascii=False),
                config=json.dumps(data.get('config', {}), ensure_ascii=False),
                enabled=data.get('enabled', True),
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            start_scheduler()
            return jsonify({'success': True, 'data': {'id': task.id}})
        finally:
            db.close()
    
    @app.route('/api/tasks/<int:task_id>', methods=['PUT'])
    def update_task(task_id):
        from models import MonitorTask
        db = SessionLocal()
        try:
            task = db.query(MonitorTask).filter(MonitorTask.id == task_id).first()
            if not task: return jsonify({'error': '任务不存在'}), 404
            data = request.json
            for k in ['name','task_type','schedule','enabled']:
                if k in data: setattr(task, k, data[k])
            if 'codes' in data: task.codes = json.dumps(data['codes'], ensure_ascii=False)
            if 'agent_ids' in data: task.agent_ids = json.dumps(data['agent_ids'], ensure_ascii=False)
            if 'config' in data: task.config = json.dumps(data['config'], ensure_ascii=False)
            task.updated_at = datetime.now()
            db.commit()
            return jsonify({'success': True})
        finally:
            db.close()
    
    @app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
    def delete_task(task_id):
        from models import MonitorTask
        db = SessionLocal()
        try:
            task = db.query(MonitorTask).filter(MonitorTask.id == task_id).first()
            if not task: return jsonify({'error': '任务不存在'}), 404
            db.delete(task)
            db.commit()
            return jsonify({'success': True})
        finally:
            db.close()
    
    @app.route('/api/tasks/<int:task_id>/trigger', methods=['POST'])
    def trigger_task(task_id):
        threading.Thread(target=_run_single_task, args=(task_id,), daemon=True).start()
        return jsonify({'success': True, 'message': '任务已触发'})
    
    @app.route('/api/tasks/<int:task_id>/logs', methods=['GET'])
    def list_task_logs(task_id):
        from models import TaskLog
        db = SessionLocal()
        try:
            limit = int(request.args.get('limit', 20))
            logs = db.query(TaskLog).filter(TaskLog.task_id == task_id)\
                .order_by(TaskLog.started_at.desc()).limit(limit).all()
            return jsonify({
                'success': True,
                'data': [{
                    'id': l.id, 'status': l.status,
                    'triggered_count': l.triggered_count,
                    'result': json.loads(l.result) if l.result else {},
                    'started_at': l.started_at.isoformat(),
                    'finished_at': l.finished_at.isoformat() if l.finished_at else None,
                } for l in logs]
            })
        finally:
            db.close()
    
    @app.route('/api/tasks/alerts', methods=['GET'])
    def get_alerts():
        """获取最近的盯盘提醒"""
        limit = int(request.args.get('limit', 20))
        return jsonify({'success': True, 'data': get_recent_alerts(limit)})
    
    # ==================== 板块数据 API ====================
    
    @app.route('/api/sectors', methods=['GET'])
    def list_sectors():
        """获取所有板块列表"""
        return jsonify({'success': True, 'data': get_sector_names()})
    
    @app.route('/api/sectors/<path:sector_name>', methods=['GET'])
    def get_sector_detail(sector_name):
        """获取指定板块的成分股"""
        from urllib.parse import unquote
        name = unquote(sector_name)
        stocks = get_sector_stocks(name)
        last_update = get_last_update_time()
        return jsonify({'success': True, 'name': name, 'stocks': stocks, 'count': len(stocks), 'last_update': last_update})
    
    @app.route('/api/sectors/update', methods=['POST'])
    def trigger_sector_update():
        """强制更新板块数据"""
        success = update_sectors_from_network()
        return jsonify({'success': success, 'message': '板块数据更新成功' if success else '更新失败，使用缓存/默认数据'})
    
    @app.route('/api/sectors/performance', methods=['GET'])
    def sector_performance():
        """获取板块表现排名（基于成分股实时行情计算，缓存60秒）"""
        from data_fetchers import get_realtime_data
        import time as time_module
        
        now = time_module.time()
        if hasattr(sector_performance, '_cache') and hasattr(sector_performance, '_cache_time'):
            if now - sector_performance._cache_time < 60:
                return jsonify({'success': True, 'data': sector_performance._cache, 'total': len(sector_performance._cache), 'cached': True})
        
        result = []
        sectors = get_all_sectors_with_stocks()
        
        def calc_sector_return(name, data):
            stocks = data.get('stocks', [])
            if not stocks:
                return None
            total_change = 0
            valid = 0
            for s in stocks[:5]:
                try:
                    rt = get_realtime_data(s['code'])
                    if rt and rt.get('change_percent') is not None:
                        total_change += rt['change_percent']
                        valid += 1
                except:
                    pass
                time_module.sleep(0.05)
            if valid == 0:
                return None
            return {'name': name, 'avg_change': round(total_change / valid, 2), 'valid_stocks': valid, 'total_stocks': len(stocks)}
        
        for name, data in sectors.items():
            r = calc_sector_return(name, data)
            if r:
                result.append(r)
        
        result.sort(key=lambda x: x['avg_change'], reverse=True)
        sector_performance._cache = result
        sector_performance._cache_time = time_module.time()
        return jsonify({'success': True, 'data': result, 'total': len(result)})

    @app.route('/api/sectors/stock/<code>', methods=['GET'])
    def sector_by_stock(code):
        """根据股票代码查询所属板块（本地数据优先，远程API兜底）"""
        try:
            code_str = str(code).strip().zfill(6)
            
            # 1. 先从本地板块数据查找（跳过全市场分组）
            sectors = get_all_sectors_with_stocks()
            skip_names = {'全部A股', '深市主板', '沪市主板', '科创板', '创业板', '沪深300权重'}
            result = None
            for name, data in sectors.items():
                if name in skip_names:
                    continue
                for s in data.get('stocks', []):
                    if s['code'] == code_str or s['code'] == code:
                        result = name
                        break
                if result:
                    break
            if result:
                return jsonify({'code': code, 'sector': result, 'success': True})
            
            # 2. 尝试从新浪API获取行业信息
            try:
                from data_fetchers import get_sector_info
                info = get_sector_info(code_str)
                if info and info.get('sector'):
                    return jsonify({'code': code, 'sector': info['sector'], 'success': True})
                if info and info.get('industry'):
                    return jsonify({'code': code, 'sector': info['industry'], 'success': True})
            except Exception:
                pass
            
            return jsonify({'code': code, 'sector': None, 'success': True})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/market/outlook', methods=['GET'])
    def market_outlook():
        """大盘研判：6个月走势分析 + 牛熊预测"""
        import time as time_module, math
        
        now = time_module.time()
        if hasattr(market_outlook, '_cache') and hasattr(market_outlook, '_cache_time'):
            if now - market_outlook._cache_time < 180:
                return jsonify({'success': True, **market_outlook._cache, 'cached': True})
        
        # 获取上证指数日K线（6个月 ≈ 120个交易日）
        from data_fetchers import get_daily_kline
        df = get_daily_kline('000001', count=180)
        
        if df is None or df.empty:
            return jsonify({'success': False, 'error': '无法获取大盘数据'}), 500
        
        # 基础计算
        data = df.tail(180).copy()
        close = data['close'].values
        volume = data['volume'].values
        
        # MA指标
        ma20 = sum(close[-20:]) / min(20, len(close))
        ma60 = sum(close[-60:]) / min(60, len(close))
        ma120 = sum(close[-120:]) / min(120, len(close))
        cur_price = float(close[-1])
        
        # 价格位置分析
        high_6m = float(max(close[-120:]))
        low_6m = float(min(close[-120:]))
        pos_pct = (cur_price - low_6m) / (high_6m - low_6m) * 100 if high_6m != low_6m else 50
        
        # 趋势分析
        pct_30d = (cur_price - close[-30]) / close[-30] * 100 if len(close) >= 30 else 0
        pct_60d = (cur_price - close[-60]) / close[-60] * 100 if len(close) >= 60 else 0
        pct_120d = (cur_price - close[-120]) / close[-120] * 100 if len(close) >= 120 else 0
        
        # 成交量趋势
        vol_avg_60 = sum(volume[-60:]) / min(60, len(volume))
        vol_avg_20 = sum(volume[-20:]) / min(20, len(volume))
        vol_ratio = vol_avg_20 / vol_avg_60 if vol_avg_60 > 0 else 1
        
        # 波动率
        returns = [(close[i] - close[i-1]) / close[i-1] * 100 for i in range(1, len(close))]
        volatility = math.sqrt(sum(r**2 for r in returns) / len(returns)) if returns else 0
        
        # 牛熊评分 (-100 ~ +100)
        score = 0
        reasons = []
        
        # 1. 价格 vs MA60
        if cur_price > ma60:
            score += 20
            reasons.append(f"价格在MA60之上（{cur_price:.0f} > {ma60:.0f}），中期趋势偏多")
        else:
            score -= 20
            reasons.append(f"价格在MA60之下（{cur_price:.0f} < {ma60:.0f}），中期趋势偏空")
        
        # 2. 价格 vs MA120
        if cur_price > ma120:
            score += 15
            reasons.append(f"价格在MA120（年线）之上，长期趋势偏多")
        else:
            score -= 15
            reasons.append(f"价格在MA120（年线）之下，长期趋势偏空")
        
        # 3. MA20 vs MA60 金叉/死叉
        if ma20 > ma60:
            score += 15
            reasons.append("MA20上穿MA60，短期均线多头排列")
        else:
            score -= 10
            reasons.append("MA20在MA60下方，短期均线偏空")
        
        # 4. 近30天涨跌
        if pct_30d > 3:
            score += 15
            reasons.append(f"近1月上涨{pct_30d:.1f}%，短期强势")
        elif pct_30d > 0:
            score += 5
            reasons.append(f"近1月微涨{pct_30d:.1f}%，短期稳定")
        elif pct_30d > -5:
            score -= 10
            reasons.append(f"近1月下跌{pct_30d:.1f}%，短期走弱")
        else:
            score -= 20
            reasons.append(f"近1月大跌{pct_30d:.1f}%，短期弱势明显")
        
        # 5. 近60天涨跌
        if pct_60d > 5:
            score += 10
            reasons.append(f"近2月上涨{pct_60d:.1f}%，中期向上")
        elif pct_60d > -3:
            score += 0
        else:
            score -= 10
            reasons.append(f"近2月下跌{pct_60d:.1f}%，中期承压")
        
        # 6. 价格位置
        if pos_pct > 70:
            score -= 10  # 高位
            reasons.append(f"价格处于近6月高位({pos_pct:.0f}%)，追高风险")
        elif pos_pct < 30:
            score += 15  # 低位
            reasons.append(f"价格处于近6月低位({pos_pct:.0f}%)，超跌布局机会")
        else:
            score += 5
            reasons.append(f"价格处于近6月中位({pos_pct:.0f}%)，走势中性")
        
        # 7. 成交量
        if vol_ratio > 1.3:
            score += 10
            reasons.append(f"近20日成交量较60日均值放量{vol_ratio:.1f}倍，资金活跃")
        elif vol_ratio < 0.7:
            score -= 10
            reasons.append(f"近20日成交量萎缩至60日均值的{vol_ratio:.1f}%，市场观望")
        
        # 8. 波动率
        if volatility > 2:
            score -= 5
            reasons.append(f"波动率偏高({volatility:.1f}%)，市场情绪不稳")
        
        score = max(-100, min(100, score))
        
        # 判定
        if score >= 30:
            market_status = "bull"
            verdict = "📈 牛市格局"
            outlook = "技术面显示中期趋势向好，均线多头排列，量能配合，预计未来1个月震荡上行。"
            suggest = "持股为主，逢回调可适当加仓，关注量能变化和板块轮动节奏。"
        elif score >= 10:
            market_status = "bull_neutral"
            verdict = "↗️ 偏强震荡"
            outlook = "市场整体偏强但存在分歧，上方有一定压力。预计未来1个月以震荡偏强为主，结构性机会突出。"
            suggest = "保持中等仓位，精选强势板块和个股，关注政策催化方向。"
        elif score >= -10:
            market_status = "neutral"
            verdict = "➡️ 震荡整理"
            outlook = "多空力量均衡，市场缺乏明确方向。预计未来1个月继续在箱体震荡，等待突破信号。"
            suggest = "控制仓位在5成以下，高抛低吸为主，等待趋势明确。"
        elif score >= -30:
            market_status = "bear_neutral"
            verdict = "↘️ 偏弱震荡"
            outlook = "市场整体偏弱，抛压较重，反弹力度有限。预计未来1个月仍有探底可能，但深度下跌空间有限。"
            suggest = "轻仓防守为主，不宜激进抄底，关注政策底信号和成交量变化。"
        else:
            market_status = "bear"
            verdict = "📉 熊市格局"
            outlook = "技术面全面走弱，均线空头排列，市场信心不足。预计未来1个月将继续探底，需等待企稳信号。"
            suggest = "严格控制仓位，现金为王，关注避险板块，耐心等待市场底的确认。"
        
        # 最近行情
        recent_k = []
        for _, row in data.tail(30).iterrows():
            recent_k.append({
                'date': str(row.get('date', row.get('day', '')))[:10],
                'close': float(row['close']),
                'volume': float(row['volume'])
            })
        
        result = {
            'market_status': market_status,
            'verdict': verdict,
            'score': score,
            'cur_price': round(cur_price, 2),
            'ma20': round(ma20, 2),
            'ma60': round(ma60, 2),
            'ma120': round(ma120, 2),
            'high_6m': round(high_6m, 2),
            'low_6m': round(low_6m, 2),
            'pct_30d': round(pct_30d, 2),
            'pct_60d': round(pct_60d, 2),
            'pct_120d': round(pct_120d, 2),
            'volatility': round(volatility, 2),
            'vol_ratio': round(vol_ratio, 2),
            'outlook': outlook,
            'suggest': suggest,
            'reasons': reasons[:6],  # 取前6条理由
            'recent_kline': recent_k[-20:],  # 最近20个交易日
        }
        
        market_outlook._cache = result
        market_outlook._cache_time = time_module.time()
        return jsonify({'success': True, **result})

    # ═══════════════════════════════════════════════════════════
    # 模拟盘系统 API
    # ═══════════════════════════════════════════════════════════

    @app.route("/api/paper/accounts", methods=["GET"])
    def get_paper_accounts_api():
        """获取所有模拟盘账户"""
        try:
            from db import get_paper_accounts as _get_accounts
            db = next(get_db())
            accounts = _get_accounts(db)
            results = []
            for acc in accounts:
                d = {c.name: getattr(acc, c.name) for c in acc.__table__.columns}
                for k, v in d.items():
                    if isinstance(v, datetime): d[k] = v.isoformat()
                # 附加持仓数
                from db import get_paper_positions as _get_positions
                positions = _get_positions(db, acc.id)
                d["position_count"] = len(positions)
                results.append(d)
            return jsonify({"accounts": results})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/paper/accounts", methods=["POST"])
    def create_paper_account_api():
        """创建模拟盘账户"""
        try:
            data = request.get_json()
            if not data or not data.get("name"):
                return jsonify({"error": "账户名称不能为空"}), 400
            from db import create_paper_account as _create
            db = next(get_db())
            account = _create(
                db,
                name=data["name"],
                initial_capital=float(data.get("initial_capital", 1000000)),
                strategy_id=data.get("strategy_id"),
                snapshot_interval=int(data.get("snapshot_interval", 60)),
                include_etf_replacement=bool(data.get("include_etf_replacement", True)),
                auto_trade=bool(data.get("auto_trade", False)),
            )
            result = {c.name: getattr(account, c.name) for c in account.__table__.columns}
            for k, v in result.items():
                if isinstance(v, datetime): result[k] = v.isoformat()
            return jsonify({"account": result}), 201
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/paper/accounts/<int:account_id>", methods=["PUT"])
    def update_paper_account_api(account_id):
        """更新模拟盘账户"""
        try:
            data = request.get_json()
            from db import update_paper_account as _update
            db = next(get_db())
            account = _update(db, account_id, **data)
            if not account:
                return jsonify({"error": "账户不存在"}), 404
            result = {c.name: getattr(account, c.name) for c in account.__table__.columns}
            for k, v in result.items():
                if isinstance(v, datetime): result[k] = v.isoformat()
            return jsonify({"account": result})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/paper/accounts/<int:account_id>", methods=["DELETE"])
    def delete_paper_account_api(account_id):
        """删除模拟盘账户"""
        try:
            from db import delete_paper_account as _delete
            db = next(get_db())
            if _delete(db, account_id):
                return jsonify({"success": True, "message": "账户已删除"})
            return jsonify({"error": "账户不存在"}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/paper/accounts/<int:account_id>/positions", methods=["GET"])
    def get_paper_positions_api(account_id):
        """获取模拟盘持仓"""
        try:
            from db import get_paper_positions as _get
            db = next(get_db())
            positions = _get(db, account_id)
            results = []
            for p in positions:
                d = {c.name: getattr(p, c.name) for c in p.__table__.columns}
                for k, v in d.items():
                    if isinstance(v, datetime): d[k] = v.isoformat()
                results.append(d)
            return jsonify({"positions": results})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/paper/accounts/<int:account_id>/orders", methods=["GET"])
    def get_paper_orders_api(account_id):
        """获取模拟盘订单记录"""
        try:
            page = int(request.args.get("page", 1))
            per_page = int(request.args.get("per_page", 20))
            from db import get_paper_orders as _get
            db = next(get_db())
            result = _get(db, account_id, page=page, per_page=per_page)
            items = []
            for o in result["items"]:
                d = {c.name: getattr(o, c.name) for c in o.__table__.columns}
                for k, v in d.items():
                    if isinstance(v, datetime): d[k] = v.isoformat()
                items.append(d)
            return jsonify({"orders": items, "total": result["total"], "page": result["page"], "per_page": result["per_page"]})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/paper/accounts/<int:account_id>/orders", methods=["POST"])
    def create_paper_order_api(account_id):
        """模拟盘下单"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "请求数据不能为空"}), 400
            required = ["code", "direction", "price", "quantity"]
            for field in required:
                if field not in data:
                    return jsonify({"error": f"缺少必填字段: {field}"}), 400
            result = create_order(
                account_id=account_id,
                code=data["code"],
                name=data.get("name", ""),
                direction=data["direction"],
                price=float(data["price"]),
                quantity=int(data["quantity"]),
                order_type=data.get("order_type", "manual"),
                strategy_run_id=data.get("strategy_run_id"),
                note=data.get("note"),
            )
            return jsonify(result), 201
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/paper/accounts/<int:account_id>/snapshot", methods=["POST"])
    def create_paper_snapshot_api(account_id):
        """手动触发模拟盘快照"""
        try:
            snapshot = create_snapshot(account_id)
            return jsonify({"snapshot": snapshot})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/paper/accounts/<int:account_id>/equity_curve", methods=["GET"])
    def get_equity_curve_api(account_id):
        """获取模拟盘收益曲线数据"""
        try:
            limit = int(request.args.get("limit", 200))
            curve = get_equity_curve(account_id, limit=limit)
            summary = get_account_summary(account_id)
            return jsonify({"curve": curve, "summary": summary})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/paper/accounts/<int:account_id>/summary", methods=["GET"])
    def get_paper_account_summary_api(account_id):
        """获取模拟盘账户摘要"""
        try:
            summary = get_account_summary(account_id)
            return jsonify({"summary": summary})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/paper/etf-map", methods=["GET"])
    def get_etf_maps_api():
        """获取所有ETF映射"""
        try:
            from db import get_etf_maps as _get
            db = next(get_db())
            maps = _get(db)
            results = []
            for m in maps:
                d = {c.name: getattr(m, c.name) for c in m.__table__.columns}
                for k, v in d.items():
                    if isinstance(v, datetime): d[k] = v.isoformat()
                results.append(d)
            return jsonify({"etf_maps": results})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/paper/etf-map", methods=["POST"])
    def create_etf_map_api():
        """创建ETF映射"""
        try:
            data = request.get_json()
            if not data or not data.get("original_code") or not data.get("etf_code"):
                return jsonify({"error": "original_code 和 etf_code 不能为空"}), 400
            from db import create_etf_map as _create
            db = next(get_db())
            mapping = _create(
                db,
                original_code=data["original_code"],
                original_name=data.get("original_name", ""),
                etf_code=data["etf_code"],
                etf_name=data.get("etf_name", ""),
                ratio=float(data.get("ratio", 1.0)),
            )
            result = {c.name: getattr(mapping, c.name) for c in mapping.__table__.columns}
            for k, v in result.items():
                if isinstance(v, datetime): result[k] = v.isoformat()
            return jsonify({"etf_map": result}), 201
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/paper/etf-map/<int:map_id>", methods=["DELETE"])
    def delete_etf_map_api(map_id):
        """删除ETF映射"""
        try:
            from db import delete_etf_map as _delete
            db = next(get_db())
            if _delete(db, map_id):
                return jsonify({"success": True})
            return jsonify({"error": "映射不存在"}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/paper/etf-map/search", methods=["GET"])
    def search_etf_map_api():
        """搜索股票代码的ETF替代"""
        try:
            code = request.args.get("code", "")
            if not code:
                return jsonify({"error": "请输入股票代码"}), 400
            from db import search_etf_replacement as _search
            db = next(get_db())
            result = _search(db, code)
            if result:
                if hasattr(result, "__table__"):
                    d = {c.name: getattr(result, c.name) for c in result.__table__.columns}
                    for k, v in d.items():
                        if isinstance(v, datetime): d[k] = v.isoformat()
                    return jsonify({"result": d})
                return jsonify({"result": result})
            return jsonify({"result": None, "message": "未找到匹配的ETF替代"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/strategy/apply_to_paper", methods=["POST"])
    def apply_strategy_to_paper_api():
        """将策略分析信号应用到模拟盘
        
        Request body:
        {
            "account_id": 1,
            "signals": [
                {"code": "600519", "name": "贵州茅台", "direction": "buy", "price": 1800.0, "quantity": 100, "note": "策略信号"},
                {"code": "688981", "name": "中芯国际", "direction": "buy", "price": 60.0, "quantity": 500}
            ],
            "strategy_run_id": "optional-strategy-run-id"
        }
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "请求数据不能为空"}), 400
            if "account_id" not in data or "signals" not in data:
                return jsonify({"error": "缺少必填字段: account_id, signals"}), 400
            
            from paper_trading import create_order as _create_order
            
            account_id = int(data["account_id"])
            strategy_run_id = data.get("strategy_run_id")
            signals = data["signals"]
            
            if not isinstance(signals, list) or len(signals) == 0:
                return jsonify({"error": "signals 必须是至少包含一个信号的数组"}), 400
            
            results = []
            errors = []
            
            for i, signal in enumerate(signals):
                try:
                    if not all(k in signal for k in ["code", "direction", "price", "quantity"]):
                        raise ValueError("缺少必填字段: code, direction, price, quantity")
                    
                    result = _create_order(
                        account_id=account_id,
                        code=signal["code"],
                        name=signal.get("name", ""),
                        direction=signal["direction"],
                        price=float(signal["price"]),
                        quantity=int(signal["quantity"]),
                        order_type="signal",
                        strategy_run_id=strategy_run_id,
                        note=signal.get("note", f"策略信号 #{i+1}"),
                    )
                    results.append(result)
                except ValueError as e:
                    errors.append({"index": i, "code": signal.get("code", ""), "error": str(e)})
                except Exception as e:
                    errors.append({"index": i, "code": signal.get("code", ""), "error": str(e)})
            
            return jsonify({
                "success": len(errors) == 0,
                "total": len(signals),
                "executed": len(results),
                "failed": len(errors),
                "results": results,
                "errors": errors
            }), 201 if len(results) > 0 else 400
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ═══════════════════════════════════════════════════════════
    # 收益排名 & 个股盈亏明细 API
    # ═══════════════════════════════════════════════════════════

    @app.route("/api/paper/profit-ranking", methods=["GET"])
    def get_profit_ranking_api():
        """获取所有模拟盘收益率排名"""
        try:
            from models import SessionLocal, PaperAccount
            db = next(get_db())
            accounts = db.query(PaperAccount).filter(
                PaperAccount.enabled == True
            ).order_by(PaperAccount.total_profit_pct.desc()).all()

            results = []
            for acc in accounts:
                days_running = 0
                if acc.created_at:
                    from datetime import date
                    days_running = (date.today() - acc.created_at.date()).days

                from db import get_paper_positions, get_paper_orders
                positions = get_paper_positions(db, acc.id)
                orders = get_paper_orders(db, acc.id, page=1, per_page=1)

                total_value = acc.cash_balance + acc.total_market_value
                total_pnl = total_value - acc.initial_capital

                results.append({
                    "account_id": acc.id,
                    "account_name": acc.name,
                    "strategy_id": acc.strategy_id,
                    "initial_capital": acc.initial_capital,
                    "total_value": round(total_value, 2),
                    "total_pnl": round(total_pnl, 2),
                    "total_profit_pct": round(acc.total_profit_pct, 2),
                    "max_drawdown": round(acc.max_drawdown, 2) if acc.max_drawdown is not None else None,
                    "win_rate": round(acc.win_rate, 2) if acc.win_rate is not None else None,
                    "stock_count": len(positions),
                    "order_count": orders["total"],
                    "days_running": days_running,
                    "snapshot_interval": acc.snapshot_interval,
                    "created_at": acc.created_at.isoformat() if acc.created_at else None,
                })

            return jsonify({"rankings": results, "total": len(results)})
        except Exception as e:
            import traceback; traceback.print_exc()
            return jsonify({"error": str(e)}), 500

    @app.route("/api/paper/accounts/<int:account_id>/profit-breakdown", methods=["GET"])
    def get_profit_breakdown_api(account_id):
        """获取指定模拟盘的个股盈亏明细"""
        try:
            from models import SessionLocal, PaperAccount, PaperOrder, PaperPosition
            db = next(get_db())
            from paper_trading import get_account_summary

            account = db.query(PaperAccount).filter(PaperAccount.id == account_id).first()
            if not account:
                return jsonify({"error": "账户不存在"}), 404

            summary = get_account_summary(account_id)
            positions = db.query(PaperPosition).filter(
                PaperPosition.account_id == account_id
            ).all()

            from collections import defaultdict
            all_orders = db.query(PaperOrder).filter(
                PaperOrder.account_id == account_id
            ).order_by(PaperOrder.created_at.asc()).all()

            stock_orders = defaultdict(list)
            for o in all_orders:
                stock_orders[o.code].append(o)

            stocks = []
            for code, orders in stock_orders.items():
                name = orders[0].name or ""
                total_buy = sum(o.amount for o in orders if o.direction == "buy")
                total_sell = sum(o.amount for o in orders if o.direction == "sell")
                total_commission = sum(o.commission for o in orders)
                total_tax = sum(o.tax for o in orders)
                buy_qty = sum(o.quantity for o in orders if o.direction == "buy")
                sell_qty = sum(o.quantity for o in orders if o.direction == "sell")

                current_position = next((p for p in positions if p.code == code), None)
                position_shares = current_position.shares if current_position else 0
                position_market_value = current_position.market_value if current_position else 0

                if buy_qty > 0:
                    avg_cost = total_buy / buy_qty
                    realized_pnl = total_sell - (avg_cost * sell_qty) - total_commission - total_tax
                else:
                    realized_pnl = total_sell - total_commission - total_tax

                if current_position and current_position.avg_cost > 0:
                    current_unrealized = (current_position.current_price - current_position.avg_cost) * current_position.shares
                else:
                    current_unrealized = 0

                total_pnl = realized_pnl + current_unrealized

                trades = []
                for o in orders:
                    trades.append({
                        "order_id": o.id,
                        "direction": o.direction,
                        "price": o.price,
                        "quantity": o.quantity,
                        "amount": o.amount,
                        "commission": o.commission,
                        "tax": o.tax,
                        "order_type": o.order_type,
                        "note": o.note,
                        "created_at": o.created_at.isoformat() if o.created_at else None,
                    })

                stocks.append({
                    "code": code,
                    "name": name,
                    "total_buy": round(total_buy, 2),
                    "total_sell": round(total_sell, 2),
                    "buy_count": buy_qty,
                    "sell_count": sell_qty,
                    "total_commission": round(total_commission, 2),
                    "total_tax": round(total_tax, 2),
                    "realized_pnl": round(realized_pnl, 2),
                    "current_position": position_shares,
                    "current_market_value": round(position_market_value, 2),
                    "current_unrealized_pnl": round(current_unrealized, 2),
                    "total_pnl": round(total_pnl, 2),
                    "trade_count": len(orders),
                    "trades": trades,
                })

            total_pnl = account.cash_balance + account.total_market_value - account.initial_capital

            return jsonify({
                "account_id": account.id,
                "account_name": account.name,
                "initial_capital": account.initial_capital,
                "total_value": round(account.cash_balance + account.total_market_value, 2),
                "cash_balance": round(account.cash_balance, 2),
                "total_pnl": round(total_pnl, 2),
                "total_profit_pct": round(account.total_profit_pct, 2),
                "max_drawdown": round(account.max_drawdown, 2) if account.max_drawdown is not None else None,
                "win_rate": round(account.win_rate, 2) if account.win_rate is not None else None,
                "stock_count": len(stocks),
                "stocks": stocks,
            })
        except Exception as e:
            import traceback; traceback.print_exc()
            return jsonify({"error": str(e)}), 500

    # ═══════════════════════════════════════════════════════════
    # 自动跟踪规则 API
    # ═══════════════════════════════════════════════════════════

    @app.route("/api/paper/accounts/<int:account_id>/auto-rules", methods=["GET"])
    def get_auto_rules_api(account_id):
        """获取指定模拟盘的自动跟踪规则"""
        try:
            from db import get_auto_rules
            db = next(get_db())
            rules = get_auto_rules(db, account_id=account_id)
            results = []
            for r in rules:
                d = {c.name: getattr(r, c.name) for c in r.__table__.columns}
                for k, v in d.items():
                    if isinstance(v, datetime): d[k] = v.isoformat()
                results.append(d)
            return jsonify({"rules": results})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/paper/accounts/<int:account_id>/auto-rules", methods=["POST"])
    def create_auto_rule_api(account_id):
        """创建自动跟踪规则"""
        try:
            data = request.get_json()
            if not data or not data.get("code"):
                return jsonify({"error": "股票代码不能为空"}), 400
            from db import create_auto_rule
            db = next(get_db())
            rule = create_auto_rule(
                db, account_id=account_id,
                code=data["code"], name=data.get("name"),
                buy_price_low=data.get("buy_price_low"),
                buy_price_high=data.get("buy_price_high"),
                buy_quantity=int(data.get("buy_quantity", 100)),
                buy_enabled=bool(data.get("buy_enabled", True)),
                sell_target_price=data.get("sell_target_price"),
                sell_stop_loss=data.get("sell_stop_loss"),
                sell_enabled=bool(data.get("sell_enabled", True)),
                max_position=int(data.get("max_position", 0)),
                note=data.get("note"),
            )
            result = {c.name: getattr(rule, c.name) for c in rule.__table__.columns}
            for k, v in result.items():
                if isinstance(v, datetime): result[k] = v.isoformat()
            return jsonify({"rule": result}), 201
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/paper/auto-rules/<int:rule_id>", methods=["PUT"])
    def update_auto_rule_api(rule_id):
        """更新自动跟踪规则"""
        try:
            data = request.get_json()
            from db import update_auto_rule
            db = next(get_db())
            rule = update_auto_rule(db, rule_id, **data)
            if not rule:
                return jsonify({"error": "规则不存在"}), 404
            result = {c.name: getattr(rule, c.name) for c in rule.__table__.columns}
            for k, v in result.items():
                if isinstance(v, datetime): result[k] = v.isoformat()
            return jsonify({"rule": result})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/paper/auto-rules/<int:rule_id>", methods=["DELETE"])
    def delete_auto_rule_api(rule_id):
        """删除自动跟踪规则"""
        try:
            from db import delete_auto_rule
            db = next(get_db())
            if delete_auto_rule(db, rule_id):
                return jsonify({"success": True})
            return jsonify({"error": "规则不存在"}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ═══════════════════════════════════════════════════════════
    # 股票推荐 API
    # ═══════════════════════════════════════════════════════════

    @app.route("/api/recommendations", methods=["GET"])
    def get_recommendations_api():
        """获取推荐列表"""
        try:
            rec_type = request.args.get("type", "daily")
            strategy = request.args.get("strategy")
            limit = int(request.args.get("limit", 50))
            from db import get_recommendations
            db = next(get_db())
            total, items = get_recommendations(db, rec_type=rec_type, strategy=strategy, limit=limit)
            results = []
            for r in items:
                d = {c.name: getattr(r, c.name) for c in r.__table__.columns}
                for k, v in d.items():
                    if isinstance(v, datetime): d[k] = v.isoformat()
                results.append(d)
            return jsonify({"recommendations": results, "total": total})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/recommendations/generate", methods=["POST"])
    def generate_recommendations_api():
        """触发推荐生成"""
        try:
            data = request.get_json() or {}
            rec_type = data.get("type", "daily")
            strategies = data.get("strategies")
            top_n = int(data.get("top_n", 10))
            import importlib, stock_screener
            importlib.reload(stock_screener)
            result = stock_screener.generate_recommendations(strategies, top_n=top_n)

            from db import save_recommendations
            db = next(get_db())
            count = 0
            for sname, sdata in result["strategies"].items():
                ids = save_recommendations(db, rec_type, sname, sdata["picks"])
                count += len(ids)
            return jsonify({
                "success": True, "count": count,
                "total_unique": result["total_unique"],
                "strategies": list(result["strategies"].keys()),
            })
        except Exception as e:
            import traceback; traceback.print_exc()
            return jsonify({"error": str(e)}), 500

    @app.route("/api/recommendations/latest", methods=["GET"])
    def get_latest_recommendations_api():
        """获取每种策略最新的推荐"""
        try:
            rec_type = request.args.get("type", "daily")
            from db import get_latest_recommendations
            db = next(get_db())
            results = get_latest_recommendations(db, rec_type=rec_type)
            output = {}
            for sname, items in results.items():
                output[sname] = []
                for r in items:
                    d = {c.name: getattr(r, c.name) for c in r.__table__.columns}
                    for k, v in d.items():
                        if isinstance(v, datetime): d[k] = v.isoformat()
                    output[sname].append(d)
            return jsonify({"strategies": output})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ═══════════════════════════════════════════════════════════
    # 回测 API
    # ═══════════════════════════════════════════════════════════

    @app.route('/api/backtest/presets', methods=['GET'])
    def backtest_presets():
        """获取可用的回测策略预设"""
        from backtest_engine import STRATEGY_PRESETS
        return jsonify({"presets": [
            {"key": k, **v} for k, v in STRATEGY_PRESETS.items()
        ]})

    @app.route('/api/backtest/run', methods=['POST'])
    def run_backtest_api():
        """执行回测"""
        import traceback
        try:
            data = request.json
            if not data or not data.get('code') or not data.get('strategy'):
                return jsonify({"error": "缺少必要参数"}), 400

            from backtest_engine import run_backtest
            result = run_backtest(
                code=data['code'],
                strategy_type=data['strategy'],
                params=data.get('params', {}),
                initial_capital=float(data.get('initial_capital', 100000)),
                start_date=data.get('start_date'),
                end_date=data.get('end_date'),
                max_data_days=int(data.get('max_data_days', 720)),
            )
            
            if not result.get('success'):
                return jsonify(result), 400
            
            return jsonify(result)
        except Exception as e:
            traceback.print_exc()
            return jsonify({"success": False, "error": str(e)}), 500

    # ═══════════════════════════════════════════════════════════
    # 买卖计划 API
    # ═══════════════════════════════════════════════════════════

    @app.route('/api/forecast', methods=['POST'])
    def forecast_api():
        """预测未来买卖信号"""
        import traceback
        try:
            data = request.json
            if not data or not data.get('code') or not data.get('strategy'):
                return jsonify({"error": "缺少必要参数"}), 400
            from backtest_engine import run_forecast
            result = run_forecast(
                code=data['code'],
                strategy_type=data['strategy'],
                params=data.get('params', {}),
                forecast_days=int(data.get('forecast_days', 22)),
            )
            if not result.get('success'):
                return jsonify(result), 400
            return jsonify(result)
        except Exception as e:
            traceback.print_exc()
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route('/api/paper/plans/<int:account_id>', methods=['GET'])
    def list_paper_plans(account_id):
        from db import get_paper_plans, get_paper_account
        db = next(get_db())
        try:
            account = get_paper_account(db, account_id)
            if not account: return jsonify({"error": "账户不存在"}), 404
            code = request.args.get('code')
            status = request.args.get('status')
            plans = get_paper_plans(db, account_id, code=code, status=status)
            result = []
            for p in plans:
                result.append({'id': p.id, 'code': p.code, 'name': p.name,
                    'direction': p.direction, 'target_price': p.target_price,
                    'quantity': p.quantity, 'reason': p.reason, 'status': p.status,
                    'created_at': p.created_at.strftime('%Y-%m-%d %H:%M:%S') if p.created_at else ''})
            return jsonify({"plans": result, "count": len(result)})
        finally: db.close()

    @app.route('/api/paper/plans/<int:account_id>', methods=['POST'])
    def create_paper_plan_api(account_id):
        from db import create_paper_plan, get_paper_account
        db = next(get_db())
        try:
            account = get_paper_account(db, account_id)
            if not account: return jsonify({"error": "账户不存在"}), 404
            data = request.json
            if not data or not data.get('code') or not data.get('direction'):
                return jsonify({"error": "缺少必填字段"}), 400
            quantity = data.get('quantity', 0)
            if quantity == 0 and data.get('direction') == 'buy':
                price = data.get('target_price', 0)
                if price > 0 and account.cash_balance > 0:
                    quantity = max(100, int(account.cash_balance * 0.3 / price / 100) * 100)
            plan = create_paper_plan(db, account_id=account_id,
                code=data['code'], name=data.get('name'), direction=data['direction'],
                target_price=data.get('target_price', 0), quantity=quantity, reason=data.get('reason'))
            return jsonify({"plan": {'id': plan.id, 'code': plan.code, 'name': plan.name,
                'direction': plan.direction, 'target_price': plan.target_price,
                'quantity': plan.quantity, 'reason': plan.reason, 'status': plan.status}}), 201
        finally: db.close()

    @app.route('/api/paper/plans/<int:account_id>/batch', methods=['POST'])
    def batch_create_plans(account_id):
        from db import create_paper_plan, get_paper_account
        db = next(get_db())
        try:
            account = get_paper_account(db, account_id)
            if not account: return jsonify({"error": "账户不存在"}), 404
            data = request.json
            if not data or not data.get('code'): return jsonify({"error": "缺少股票代码"}), 400
            code, name = data['code'], data.get('name', code)
            cp = data.get('current_price', 0)
            if cp <= 0:
                from data_fetchers import get_realtime_data
                try:
                    rt = get_realtime_data(code)
                    if rt and rt.get('current_price'): cp = rt['current_price']
                except: pass
            if cp <= 0: return jsonify({"error": "无法获取当前价格"}), 400
            cash = account.cash_balance
            qty = data.get('quantity', 0)
            if qty == 0: qty = max(100, int(cash * 0.3 / cp / 100) * 100)
            created = []
            bp = create_paper_plan(db, account_id, code, name, 'buy', cp, qty, reason=f"强势股策略推荐买入，当前价{cp:.2f}")
            created.append({'id': bp.id, 'direction': 'buy', 'target_price': cp, 'quantity': qty, 'reason': bp.reason})
            tp = round(cp * 1.15, 2)
            sp = create_paper_plan(db, account_id, code, name, 'sell', tp, qty, reason=f"止盈目标价（+15%），预期涨幅15%")
            created.append({'id': sp.id, 'direction': 'sell', 'target_price': tp, 'quantity': qty, 'reason': sp.reason})
            sl = round(cp * 0.93, 2)
            s2 = create_paper_plan(db, account_id, code, name, 'sell', sl, qty, reason=f"止损价（-7%），控制回撤风险")
            created.append({'id': s2.id, 'direction': 'sell', 'target_price': sl, 'quantity': qty, 'reason': s2.reason})
            return jsonify({"plans": created, "count": len(created)}), 201
        finally: db.close()

    @app.route('/api/paper/plans/<int:plan_id>/status', methods=['PUT'])
    def update_plan_status_api(plan_id):
        from db import update_plan_status
        db = next(get_db())
        try:
            data = request.json
            st = data.get('status', 'pending')
            if st not in ('pending', 'partial', 'executed', 'cancelled'): return jsonify({"error": "无效状态"}), 400
            plan = update_plan_status(db, plan_id, st)
            if not plan: return jsonify({"error": "计划不存在"}), 404
            return jsonify({"plan": {'id': plan.id, 'status': plan.status}})
        finally: db.close()

    # ─── 基本面与因子分析 ───

    @app.route('/api/fundamentals/<code>')
    def get_fundamentals(code):
        """获取最新财务数据（db缓存优先，无缓存时自动拉取）"""
        try:
            code_str = str(code).strip()
            db = next(get_db())
            try:
                data = get_latest_financial(db, code_str)
                if not data:
                    data = fetch_and_cache(code_str, db)
                return jsonify(data if data else {})
            finally:
                db.close()
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 获取财务数据失败: {error_msg}")
            return jsonify({'error': '获取数据失败', 'message': error_msg}), 500

    @app.route('/api/factor/rating/<code>')
    def get_factor_rating(code):
        """获取多因子综合评级"""
        try:
            code_str = str(code).strip()
            rating = get_stock_rating(code_str)
            return jsonify(rating)
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 获取因子评级失败: {error_msg}")
            return jsonify({'error': '获取数据失败', 'message': error_msg}), 500

    @app.route('/api/factor/rating_text/<code>')
    def get_factor_rating_text(code):
        """获取多因子评级文本（用于AI注入）"""
        try:
            code_str = str(code).strip()
            text = get_rating_text(code_str)
            return jsonify({'code': code_str, 'text': text})
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 获取因子评级文本失败: {error_msg}")
            return jsonify({'error': '获取数据失败', 'message': error_msg}), 500

    # ─── 信号融合 ───

    @app.route('/api/signal/fuse', methods=['POST'])
    def signal_fuse():
        """融合多源信号策略"""
        try:
            data = request.json
            if not data:
                return jsonify({'error': '缺少请求体'}), 400

            results = {}
            if 'code' in data:
                code = str(data['code']).strip()
                results[code] = fuse_signals(code, db=next(get_db()))
            elif 'codes' in data:
                for code in data['codes']:
                    code_str = str(code).strip()
                    results[code_str] = fuse_signals(code_str, db=next(get_db()))
            else:
                return jsonify({'error': '缺少 code 或 codes 字段'}), 400

            return jsonify({'results': results})
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 信号融合失败: {error_msg}")
            return jsonify({'error': '处理失败', 'message': error_msg}), 500

    # ─── 策略网格搜索 ───

    @app.route('/api/strategy/grid_search', methods=['POST'])
    def strategy_grid_search():
        """策略参数网格搜索优化"""
        try:
            data = request.json
            if not data:
                return jsonify({'error': '缺少请求体'}), 400

            code = str(data.get('code', '')).strip()
            if not code:
                return jsonify({'error': '缺少股票代码'}), 400

            strategy_type = str(data.get('strategy_type', 'ma_cross')).strip()
            param_grid = data.get('param_grid')

            result = grid_search(code, strategy_type, param_grid)
            return jsonify(result)
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 网格搜索失败: {error_msg}")
            return jsonify({'error': '处理失败', 'message': error_msg}), 500

    # ─── 批量回测 ───

    @app.route('/api/strategy/batch_backtest', methods=['POST'])
    def strategy_batch_backtest():
        """批量回测（多股票）"""
        try:
            data = request.json or {}
            codes = data.get('codes', [])
            if not codes:
                return jsonify({'error': '缺少股票代码列表'}), 400
            strategy_type = str(data.get('strategy_type', 'ma_cross')).strip()
            params = data.get('params')
            result = batch_backtest(codes, strategy_type, params)
            return jsonify(result)
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 批量回测失败: {error_msg}")
            return jsonify({'error': '处理失败', 'message': error_msg}), 500
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 批量回测失败: {error_msg}")
            return jsonify({'error': '处理失败', 'message': error_msg}), 500

    # 策略系统路由
    register_strategy_routes(app)

    # ═══════════════════════════════════════════════════════════
    # 内置调度器路由
    # ═══════════════════════════════════════════════════════════

    @app.route("/api/scheduler/status", methods=["GET"])
    def scheduler_status():
        """查看调度器任务状态"""
        try:
            from scheduler import get_scheduler_status
            return jsonify({"success": True, "tasks": get_scheduler_status()})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/scheduler/logs", methods=["GET"])
    def scheduler_logs():
        """查看最近调度器输出"""
        try:
            limit = int(request.args.get("limit", 20))
            from scheduler import get_scheduler_outputs
            return jsonify({"success": True, "records": get_scheduler_outputs(limit)})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/scheduler/trigger", methods=["POST"])
    def scheduler_trigger():
        """手动触发调度器任务"""
        try:
            from scheduler import get_scheduler
            data = request.get_json(silent=True) or {}
            name = data.get("name", "")
            sched = get_scheduler()
            result = sched.run_task(name)
            return jsonify(result)
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    return app
