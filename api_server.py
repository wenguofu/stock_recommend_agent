#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Flask API服务 - 股票数据查询接口
使用新浪和东方财富API提供股票数据
"""

from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
import warnings
import os
import time
import traceback
import logging

warnings.filterwarnings('ignore')

# 配置日志
from logging_config import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

# 创建Flask应用
app = Flask(__name__, static_folder=None)
CORS(app)

app.config['JSON_AS_ASCII'] = False

# ── 认证中间件 ──
from auth_middleware import register_auth
register_auth(app)

# ── 统一错误处理 ──
from error_handler import register_error_handler
register_error_handler(app)

# ── 请求日志中间件 ──
@app.before_request
def log_request_start():
    request._start_time = time.time()
    # 跳过静态文件
    if request.path.startswith('/assets/') or request.path == '/vite.svg':
        return
    body_preview = ''
    if request.method in ('POST', 'PUT') and request.data:
        try:
            body_preview = ' ' + request.get_data(as_text=True)[:200]
        except:
            pass
    logger.info(f"→ {request.method} {request.path}{body_preview}")

@app.after_request
def log_request_end(response):
    if hasattr(request, '_start_time'):
        elapsed = time.time() - request._start_time
        if request.path.startswith('/assets/') or request.path == '/vite.svg':
            return response
        status = response.status_code
        level = logging.WARNING if status >= 400 else logging.INFO
        logger.log(level, f"← {request.method} {request.path} → {status} ({elapsed:.2f}s)")
    return response

@app.errorhandler(Exception)
def handle_uncaught_error(e):
    """全局未捕获异常处理"""
    tb = traceback.format_exc()
    logger.error(f"❌ 未捕获异常: {e}\n{tb}")
    return jsonify({"error": "服务器内部错误", "message": str(e)}), 500

# 前端目录
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), 'stock_frontend', 'dist')

# 前端静态文件路由
@app.route('/assets/<path:path>')
def serve_assets(path):
    return send_from_directory(os.path.join(FRONTEND_DIR, 'assets'), path)

@app.route('/vite.svg')
def serve_favicon():
    return send_from_directory(FRONTEND_DIR, 'vite.svg')

# 确保JSON响应使用UTF-8编码
app.config['JSON_AS_ASCII'] = False

# 导入并注册路由（延迟导入避免循环依赖）
def register_routes():
    from api_routes import register_routes as register
    register(app)
    # 注册AI辩论+分析API
    from debate_routes import register_debate_routes
    register_debate_routes(app)
    # 注册风险管理API
    from risk_routes import register_risk_routes
    register_risk_routes(app)
    # 注册因子+ML预测API
    from factor_routes import register_factor_routes
    register_factor_routes(app)
    # 注册中长线交易API
    from midline_routes import register_midline_routes
    register_midline_routes(app)
    # 注册推荐跟踪API
    from recommendation_tracker import register_track_routes
    register_track_routes(app)
    # 注册定量估值API
    from valuation_routes import register_valuation_routes
    register_valuation_routes(app)

def init_database():
    """初始化数据库和默认配置"""
    try:
        from init_agents import init_default_agents
        init_default_agents()
        # 确保新增表被创建
        from models import engine, Base
        from recommendation_tracker import RecommendationTrack
        Base.metadata.create_all(engine)
        print("[初始化] 数据库表已确认")
    except Exception as e:
        print(f"[初始化] 数据库初始化失败: {e}")

register_routes()
init_database()

# 启动 WebSocket 服务
from websocket_routes import init_socketio
socketio = init_socketio(app)

# 启动内置任务调度器
from scheduler import start_scheduler
scheduler = start_scheduler()
print(f"[调度器] 已启动，{len(scheduler.tasks)}个任务")

if __name__ == '__main__':
    import os
    PORT = int(os.environ.get("API_PORT", 35000))
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"
    print("=" * 60)
    print("股票数据API服务启动")
    print("=" * 60)
    print(f"REST API: http://localhost:{PORT}")
    if socketio:
        print(f"WebSocket: ws://localhost:{PORT}")
    print("调度器运行中...")
    print("=" * 60)
    if socketio:
        socketio.run(app, host='0.0.0.0', port=PORT, debug=DEBUG)
    else:
        app.run(host='0.0.0.0', port=PORT, debug=DEBUG)
