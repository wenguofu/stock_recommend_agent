#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API路由模块

⚠️  本文件 3898 行，需要逐步拆分。当前结构：
  ── 行情 API ──          GET  /api/sina/realtime|daily|minute|money_flow|...
  ── 自选股 / 配置 ──     /api/watchlist, /api/config
  ── Agent 管理 ──        /api/agents
  ── AI 辩论 / 分析 ──    /api/ai/debate|analyze  (→ 待提取至 debate_routes.py)
  ── 策略推荐 / 回测 ──   /api/strategy, /api/backtest, /api/forecast
  ── 模拟盘 ──           /api/paper/*  (部分已分离至 paper_trading.py)
  ── 板块 / 调度器 ──     /api/sectors, /api/scheduler
  ── 主线预判 ──          /api/sector-prediction

已独立模块：strategy_routes.py, risk_routes.py, factor_routes.py
待提取：debate routes (~200行), paper routes (~150行)
"""

from flask import jsonify, request
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
from datetime import datetime, date, timedelta
import json
import re
import logging
logger = logging.getLogger(__name__)
from data_fetchers import get_realtime_data, get_timeline_data, get_minute_kline, get_daily_kline, get_money_flow, get_money_flow_history, get_money_flow_realtime_kline, get_fundamental_data, get_industry_comparison, get_news_from_stock, get_guba_posts
from data_formatters import format_for_ai, to_json
from technical_indicators import get_comprehensive_data_with_indicators, get_comprehensive_data
from models import get_db, SessionLocal
from db import (
    get_watchlist, add_to_watchlist, remove_from_watchlist, update_watchlist_order, update_watchlist_position,
    get_config, set_config, get_all_configs,
    get_agents, get_agent, create_agent, update_agent, delete_agent,
    create_debate_job,
    get_strategies, get_strategy, create_strategy, update_strategy, delete_strategy, apply_strategy_to_agents,
    get_paper_accounts, get_paper_account, create_paper_account, update_paper_account, delete_paper_account,
    get_paper_positions, get_paper_orders, get_paper_snapshots,
    get_etf_maps, get_etf_map, create_etf_map, delete_etf_map, search_etf_replacement,
    get_latest_financial
)
from debate_routes import register_debate_routes, _run_debate_job, _run_multi_select_job
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
    # 修复 ARCH-07: 装饰器挂载到 LLM/重计算端点,防止暴力刷
    from rate_limiter import rate_limit
    # 修复 ARCH-02: 统一响应格式装饰器(端点可渐进式迁移)
    from error_handler import json_endpoint

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
        """健康检查(深检) — 修复 ARCH-06: 查 DB 连通性、外部 API 可达性、调度器状态、磁盘空间

        注: 不使用 @json_endpoint 是因为此端点需要返 503 状态码(degraded 场景),
        装饰器统一返 200, 不符合语义.
        """
        import shutil
        health_status = {
            'status': 'ok',
            'timestamp': datetime.now().isoformat(),
            'service': '新浪股票API服务',
            'checks': {},
        }
        overall_ok = True

        # ── 1. DB 连通性 ──
        try:
            from models import SessionLocal
            from sqlalchemy import text
            db = SessionLocal()
            try:
                db.execute(text("SELECT 1"))
                health_status['checks']['database'] = {'ok': True}
            finally:
                db.close()
        except Exception as e:
            health_status['checks']['database'] = {'ok': False, 'error': str(e)}
            overall_ok = False

        # ── 2. 外部 API ping (新浪/腾讯, 3s timeout) ──
        try:
            import requests
            r = requests.get("https://qt.gtimg.cn/q=sh000001", timeout=3)
            health_status['checks']['tencent_api'] = {
                'ok': r.status_code == 200,
                'status_code': r.status_code,
            }
            if r.status_code != 200:
                overall_ok = False
        except Exception as e:
            health_status['checks']['tencent_api'] = {'ok': False, 'error': str(e)}
            overall_ok = False

        # ── 3. 调度器状态 ──
        try:
            from scheduler import get_scheduler
            sched = get_scheduler()
            running = sched.running if hasattr(sched, 'running') else False
            health_status['checks']['scheduler'] = {
                'ok': running,
                'task_count': len(sched.tasks) if hasattr(sched, 'tasks') else 0,
            }
            if not running:
                overall_ok = False
        except Exception as e:
            health_status['checks']['scheduler'] = {'ok': False, 'error': str(e)}
            overall_ok = False

        # ── 4. 磁盘空间 (data dir, 阈值 1GB) ──
        try:
            project_root = os.path.dirname(os.path.abspath(__file__))
            usage = shutil.disk_usage(project_root)
            free_gb = usage.free / (1024 ** 3)
            health_status['checks']['disk'] = {
                'ok': free_gb > 1.0,
                'free_gb': round(free_gb, 2),
                'total_gb': round(usage.total / (1024 ** 3), 2),
            }
            if free_gb < 1.0:
                overall_ok = False
        except Exception as e:
            health_status['checks']['disk'] = {'ok': False, 'error': str(e)}

        # ── 5. 内存 (best effort) ──
        try:
            import psutil
            mem = psutil.virtual_memory()
            health_status['checks']['memory'] = {
                'percent': mem.percent,
                'available_gb': round(mem.available / (1024 ** 3), 2),
            }
        except ImportError:
            health_status['checks']['memory'] = {'ok': None, 'note': 'psutil not installed'}

        if not overall_ok:
            health_status['status'] = 'degraded'
        return jsonify(health_status), 200 if overall_ok else 503

    # 修复 ARCH-01: 抽离 sina + sentiment 路由到 realtime_routes.py
    from realtime_routes import register_realtime_routes
    register_realtime_routes(app)


    # ==================== 自选股API ====================

    @app.route('/api/watchlist', methods=['GET'])
    def get_watchlist_api():
        """获取自选股列表（支持分页）"""
        page = request.args.get('page', 1, type=int)
        pageSize = request.args.get('pageSize', 20, type=int)

        db = next(get_db())
        try:
            items = get_watchlist(db)
            total = len(items)

            # Apply pagination
            start = (page - 1) * pageSize
            end = start + pageSize
            paginated = items[start:end]

            return jsonify({
                'success': True,
                'data': [{'id': item.id, 'code': item.code, 'name': item.name,
                          'cost_price': item.cost_price, 'shares': item.shares,
                          'sort_order': item.sort_order} for item in paginated],
                'total': total,
                'page': page,
                'pageSize': pageSize,
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
            if value is None:
                return jsonify({'success': False, 'error': f'配置 {key} 不存在'}), 404
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

    # ==================== 批量行情API ====================

    @app.route('/api/stocks/batch_realtime', methods=['POST'])
    def batch_realtime():
        """批量获取实时行情 — 一次请求查询最多30只股票"""
        try:
            data = request.json or {}
            codes = data.get('codes', [])
            if not codes or len(codes) > 30:
                return jsonify({'error': 'codes参数需为1-30只股票'}), 400

            from concurrent.futures import ThreadPoolExecutor, as_completed
            results = {}
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {
                    executor.submit(get_realtime_data, str(c).strip()): c
                    for c in codes
                }
                for future in as_completed(futures):
                    code = futures[future]
                    try:
                        results[code] = future.result(timeout=8)
                    except Exception:
                        results[code] = None

            response = jsonify({'success': True, 'data': results, 'count': len(results)})
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

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

    # ==================== 策略推荐 API ====================

    @app.route('/api/strategy/recommendations')
    def get_strategy_recommendations():
        """获取三种策略的推荐股票"""
        result = {'strategies': [], 'timestamp': datetime.now().isoformat()}
        
        # 策略1: 强势股 (已有)
        try:
            limit_time = request.args.get('limit_time', '11:30')
            # 复用 get_strong_stocks 逻辑... 简化版
            strong_result = {'strategy': 'strong_stocks', 'name': '强势股接力', 
                           'description': '前两日早盘涨停, 今日未涨停的接力候选',
                           'stocks': [], 'count': 0}
            result['strategies'].append(strong_result)
        except Exception as e:
            result['strategies'].append({'strategy': 'strong_stocks', 'error': str(e), 'stocks': []})
        
        # 策略2: 十倍潜力股
        try:
            from strategies.tenbagger import screen_tenbaggers
            ten = screen_tenbaggers()
            result['strategies'].append(ten)
        except Exception as e:
            result['strategies'].append({'strategy': 'tenbagger', 'error': str(e), 'stocks': []})
        
        # 策略3: 突破形态
        try:
            from strategies.breakout import screen_breakouts
            brk = screen_breakouts()
            result['strategies'].append(brk)
        except Exception as e:
            result['strategies'].append({'strategy': 'breakout', 'error': str(e), 'stocks': []})
        
        return jsonify(result)

    @app.route('/api/strategy/<strategy_type>')
    def get_single_strategy(strategy_type):
        """获取单个策略的推荐"""
        try:
            if strategy_type == 'tenbagger':
                from strategies.tenbagger import screen_tenbaggers
                return jsonify(screen_tenbaggers())
            elif strategy_type == 'breakout':
                from strategies.breakout import screen_breakouts
                return jsonify(screen_breakouts())
            else:
                return jsonify({'error': f'未知策略: {strategy_type}'}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500

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
    # 大盘趋势监控 API (market_monitor — OpenSpec: market-trend-monitor)
    # ═══════════════════════════════════════════════════════════

    @app.route('/api/market/monitor', methods=['GET'])
    def market_monitor_full():
        """大盘趋势完整监控报告"""
        try:
            from market_monitor import full_monitor as _full_monitor
            code = request.args.get('code', 'sh000001')
            result = _full_monitor(code)
            return jsonify({'success': True, **result})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/market/monitor/quick', methods=['GET'])
    def market_monitor_quick():
        """大盘趋势轻量查询（仅预警等级+分数）"""
        try:
            from market_monitor import full_monitor as _full_monitor
            code = request.args.get('code', 'sh000001')
            result = _full_monitor(code)
            return jsonify({
                'success': True,
                'code': result.get('code', code),
                'warning_level': result.get('warning_level'),
                'total_score': result.get('total_score'),
                'verdict': result.get('verdict'),
                'suggest': result.get('suggest'),
                'signals': result.get('signals', []),
                'cur_price': result.get('cur_price'),
                'timestamp': result.get('timestamp'),
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/market/monitor/history', methods=['GET'])
    def market_monitor_history():
        """大盘各维度分数明细"""
        try:
            from market_monitor import full_monitor as _full_monitor
            code = request.args.get('code', 'sh000001')
            result = _full_monitor(code)
            checks = result.get('checks', {})
            dimensions = {}
            for name, check in checks.items():
                signal_text = check.get('detail', '')
                if not signal_text:
                    signal_text = ', '.join(check.get('signals', []))
                dimensions[name] = {
                    'score': check.get('score', 0),
                    'summary': signal_text
                }
            return jsonify({
                'success': True,
                'code': result.get('code', code),
                'current': {
                    'warning_level': result.get('warning_level'),
                    'total_score': result.get('total_score'),
                    'verdict': result.get('verdict'),
                },
                'dimensions': dimensions,
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

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
                client_order_id=data.get("client_order_id"),  # 幂等键
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
                        # 策略信号批量下单用 (strategy_run_id, code, direction) 作为幂等键
                        client_order_id=signal.get("client_order_id")
                            or f"{strategy_run_id or 'sig'}:{signal['code']}:{signal['direction']}:{i}",
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
    # 新版股票推荐 API (四层筛选)
    # ═══════════════════════════════════════════════════════════

    @app.route("/api/screening/recommend", methods=["GET"])
    def get_screening_recommendations():
        """获取精选推荐 - 四层筛选"""
        try:
            rec_type = request.args.get("type", "short")  # short | mid
            top_n = int(request.args.get("top_n", 5))
            from screening import get_recommendations
            result = get_recommendations(recommendation_type=rec_type, top_n=top_n)
            return jsonify(result)
        except Exception as e:
            import traceback; traceback.print_exc()
            return jsonify({"error": str(e)}), 500

    @app.route("/api/screening/sectors", methods=["GET"])
    def get_hot_sectors():
        """获取当前热门板块"""
        try:
            from screening import HotSectorManager
            mgr = HotSectorManager()
            return jsonify({
                "sectors": mgr.get_current_sectors(),
                "config": mgr.get_config()
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/screening/sectors/refresh", methods=["POST"])
    def refresh_hot_sectors():
        """刷新热门板块"""
        try:
            from screening import HotSectorManager
            mgr = HotSectorManager()
            result = mgr.update_weekly()
            return jsonify(result)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/screening/market-check", methods=["GET"])
    def check_market_safety():
        """检查大盘环境是否适合筛选"""
        try:
            from screening import is_market_safe_for_screening
            is_safe, details = is_market_safe_for_screening()
            return jsonify({
                "is_safe": is_safe,
                "details": details
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/screening/layer1", methods=["POST"])
    def run_layer1_screening():
        """执行Layer 1筛选"""
        try:
            rec_type = request.json.get("type", "short") if request.json else "short"
            from screening import screen_layer1
            result = screen_layer1(recommendation_type=rec_type)
            return jsonify(result)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/screening/layer2", methods=["POST"])
    def run_layer2_scoring():
        """执行Layer 2评分"""
        try:
            from screening import screen_layer1, score_layer2
            rec_type = request.json.get("type", "short") if request.json else "short"
            layer1_result = screen_layer1(recommendation_type=rec_type)
            result = score_layer2(layer1_result)
            return jsonify(result)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/monitoring/daily", methods=["GET"])
    def get_daily_monitoring():
        """获取每日监控状态"""
        try:
            from monitoring import DailyMonitor
            monitor = DailyMonitor()
            status = monitor.get_daily_status()
            return jsonify(status)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/monitoring/alerts", methods=["GET"])
    def get_monitoring_alerts():
        """获取预警列表"""
        try:
            from monitoring import AlertService
            service = AlertService()
            # 从请求获取持仓
            from models import SessionLocal
            from sqlalchemy import text
            db = SessionLocal()
            try:
                positions = db.execute(text('''
                    SELECT code, name, shares, avg_cost, current_price
                    FROM paper_positions WHERE shares > 0
                ''')).fetchall()
                pos_list = [{
                    'code': p[0], 'name': p[1], 'shares': p[2],
                    'cost': p[3], 'current_price': p[4],
                    'pnl_pct': round((p[4]/p[3]-1)*100, 2) if p[3] and p[3] > 0 and p[4] else 0
                } for p in positions]
            finally:
                db.close()
            alerts = service.check_alerts(pos_list)
            return jsonify({"alerts": alerts, "history": service.get_recent_alerts()})
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
    @rate_limit('ai_analyze')
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
                except Exception as _rt_err:
                    logger.debug(f"realtime price fetch failed for {code}: {_rt_err}")
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
    @json_endpoint('raw')
    def get_fundamentals(code):
        """获取最新财务数据（MySQL优先，毫秒级）"""
        code_str = str(code).strip()
        return get_fundamental_data(code_str) or {}

    @app.route('/api/factor/rating/<code>')
    @json_endpoint('raw')
    def get_factor_rating(code):
        """获取多因子综合评级"""
        code_str = str(code).strip()
        return get_stock_rating(code_str)

    @app.route('/api/factor/rating_text/<code>')
    @json_endpoint('raw')
    def get_factor_rating_text(code):
        """获取多因子评级文本（用于AI注入）"""
        code_str = str(code).strip()
        return {'code': code_str, 'text': get_rating_text(code_str)}

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
                db = next(get_db())
                try:
                    results[code] = fuse_signals(code, db=db)
                finally:
                    db.close()
            elif 'codes' in data:
                # 修复 BUG-04: 每次循环单独 try/finally close,避免连接池耗尽
                for code in data['codes']:
                    code_str = str(code).strip()
                    db = next(get_db())
                    try:
                        results[code_str] = fuse_signals(code_str, db=db)
                    except Exception as inner_e:
                        results[code_str] = {'error': str(inner_e)}
                        print(f"[API] signal_fuse {code_str} 失败: {inner_e}")
                    finally:
                        db.close()
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

    # 策略系统路由
    register_strategy_routes(app)

    # ═══════════════════════════════════════════════════════════
    # 内置调度器路由 — 修复 ARCH-01: 抽离到 scheduler_routes.py
    # ═══════════════════════════════════════════════════════════
    from scheduler_routes import register_scheduler_routes
    register_scheduler_routes(app)

    # 修复 ARCH-01: 抽离 sector + profile 路由到 sector_routes.py
    from sector_routes import register_sector_routes
    register_sector_routes(app)

    # ═══════════════════════════════════════════════════════════
    # StockDetail 3 Tabs 增强 — enhance-stock-detail-tabs
    #   - /api/fundamentals/<code>/history        (基本面 趋势)
    #   - /api/valuation/dcf/<code>              (基本面 DCF)
    #   - /api/sina/daily/with_benchmark/<code>  (K线 基准+形态)
    #   - /api/sentiment/analytics/<code>        (舆情 合并)
    # ═══════════════════════════════════════════════════════════
    from services.dcf import dcf_valuation
    from services.pattern_detect import detect_patterns
    from services.text_mining import extract_keywords, sentiment_index
    import db as _db_module

    @app.route('/api/fundamentals/<code>/history')
    def fundamentals_history(code):
        """基本面 tab 财务趋势数据 (多期时序)"""
        try:
            limit = int(request.args.get('limit', 8))
        except (TypeError, ValueError):
            limit = 8
        db = SessionLocal()
        try:
            rows = _db_module.get_stock_financials(db, code, limit=limit)
        finally:
            db.close()
        return jsonify({'code': code, 'history': rows or []})

    @app.route('/api/valuation/dcf/<code>')
    def valuation_dcf(code):
        """基本面 tab DCF 简易估值

        Query (canonical short naming):
          growth   - 5 年增速 (default 0.15)
          discount - 折现率   (default 0.10)
          terminal - 永续增速 (default 0.03)
        """
        try:
            growth = float(request.args.get('growth', 0.15))
            discount = float(request.args.get('discount', 0.10))
            terminal = float(request.args.get('terminal', 0.03))
        except (TypeError, ValueError):
            return jsonify({'error': '参数类型错误, 需要 float'}), 400

        realtime = get_realtime_data(code) or {}
        # realtime uses 'current_price' (not 'price'/'close'); it has no 'eps' key in
        # production, but the test fixture injects 'eps' for convenience — accept both.
        # Real path: source EPS from latest stock_financials row; fall back to 0 (DCF
        # will then error gracefully per spec).
        price = realtime.get('current_price') or realtime.get('price') or realtime.get('close') or 0
        eps = realtime.get('eps')
        if eps is None:
            eps = 0
            try:
                import db as _db_module
                db_sess = SessionLocal()
                try:
                    fin_rows = _db_module.get_stock_financials(db_sess, code, limit=1) or []
                    if fin_rows:
                        raw_eps = fin_rows[0].get('eps') if isinstance(fin_rows[0], dict) else None
                        if raw_eps is not None:
                            eps = float(raw_eps)
                finally:
                    db_sess.close()
            except Exception:
                eps = 0

        result = dcf_valuation(
            eps=eps,
            current_price=price,
            growth=growth,
            discount=discount,
            terminal=terminal,
        )
        result['code'] = code
        return jsonify(result)

    @app.route('/api/sina/daily/with_benchmark/<code>')
    def sina_daily_with_benchmark(code):
        """K线图 tab 主图 + 基准叠加 + 形态标注

        Query:
          index - 基准 code (default sh000300)
          count - 主图根数 (default 240)
        """
        index = request.args.get('index', 'sh000300')
        try:
            count = int(request.args.get('count', 240))
        except (TypeError, ValueError):
            count = 240

        stock = get_daily_kline(code, count=count) or []
        benchmark = get_daily_kline(index, count=count) if index else []

        patterns = detect_patterns(stock) if stock else []

        return jsonify({
            'stock': stock,
            'benchmark': benchmark,
            'patterns': patterns,
            'benchmark_field': index,
            'count': len(stock),
        })

    @app.route('/api/sentiment/analytics/<code>')
    def sentiment_analytics(code):
        """舆情 tab 合并接口: 情绪指数 + 关键词 + 原始新闻

        Query:
          days - 日期窗口 (default 30)
          top  - 关键词 top N (default 20)
        """
        try:
            days = int(request.args.get('days', 30))
            top = int(request.args.get('top', 20))
        except (TypeError, ValueError):
            days, top = 30, 20

        news = get_news_from_stock(code, days=days) or []
        # get_guba_posts signature: (code, latest_count, hot_count) — no 'days' kwarg.
        # Heuristic: ask for days*2 latest + days*2 hot to cover the date window.
        posts = get_guba_posts(code, latest_count=days * 2, hot_count=days * 2) or []

        # news 字段契约: 新闻 + 帖子 合并, date-window 过滤后上限 100
        # Source rows use 'time' (e.g. '2025-01-15 14:30:00'), slice first 10 chars for date.
        combined = []
        for n in news[:100]:
            combined.append({
                'date': (n.get('time') or '')[:10],
                'title': n.get('title', ''),
                'source': n.get('source', '新浪'),
            })
        for p in posts[:100]:
            combined.append({
                'date': (p.get('time') or '')[:10],
                'title': p.get('title', ''),
                'source': p.get('source', '股吧'),
            })

        # 日期窗口过滤 (now - days)
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        combined = [c for c in combined if c['date'][:10] >= cutoff]

        titles = [c['title'] for c in combined if c['title']]
        idx = sentiment_index(combined, days=days)
        kw = extract_keywords(titles, top=top)

        return jsonify({
            'index': idx,
            'keywords': kw,
            'news': combined,
        })

    return app
