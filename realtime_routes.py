#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实时行情 + 舆情路由模块 — 修复 ARCH-01: 拆 api_routes.py

从 api_routes.py 抽离的 /api/sina/* + /api/sentiment/* 端点,共 14 个:
  - GET  /api/sina/comprehensive/<code>
  - GET  /api/sina/comprehensive_with_indicators/<code>
  - GET  /api/sina/realtime/<code>
  - GET  /api/sina/timeline/<code>
  - GET  /api/sina/minute/<code>
  - GET  /api/sina/daily/<code>
  - GET  /api/sina/money_flow/<code>
  - GET  /api/sina/money_flow/history/<code>
  - GET  /api/sina/money_flow/realtime/<code>
  - GET  /api/sina/fundamental/<code>
  - GET  /api/sina/industry_comparison/<code>
  - GET  /api/sina/for_ai/<code>
  - GET  /api/sina/for_ai_with_indicators/<code>
  - GET  /api/sentiment/news/<code>
  - GET  /api/sentiment/posts/<code>
  - GET  /api/sentiment/all/<code>

依赖(全部走原 import 路径,避免重复声明):
  - data_fetchers (get_realtime_data, get_daily_kline, get_money_flow, ...)
  - data_formatters (format_for_ai)
  - technical_indicators (get_comprehensive_data_with_indicators, get_comprehensive_data)
  - sector_data, models, db, utils (is_valid_stock_code)
"""
from flask import jsonify, request
from datetime import datetime, date, timedelta
import os
import json
import re
import logging
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

from data_fetchers import (
    get_realtime_data, get_timeline_data, get_minute_kline,
    get_daily_kline, get_money_flow, get_money_flow_history,
    get_money_flow_realtime_kline, get_fundamental_data,
    get_industry_comparison, get_news_from_stock, get_guba_posts,
)
from data_formatters import format_for_ai, to_json
from technical_indicators import (
    get_comprehensive_data_with_indicators, get_comprehensive_data,
)
from models import get_db, SessionLocal
from utils import is_valid_stock_code

logger = logging.getLogger(__name__)


def register_realtime_routes(app):
    """注册实时行情 + 舆情相关路由"""

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

