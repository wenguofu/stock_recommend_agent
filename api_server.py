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
import json

warnings.filterwarnings('ignore')

# 配置日志
from logging_config import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

# 创建Flask应用
app = Flask(__name__, static_folder=None)

# 修复 numpy 类型 JSON 序列化问题
import numpy as np

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

app.json_encoder = NumpyEncoder
# 同时 patch jsonify 的 default encoder
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False

# 修复 ARCH-08: CORS 白名单,生产环境不允许任意域访问
# 优先级: 环境变量 ALLOWED_ORIGINS (逗号分隔) > 默认白名单
_default_origins = [
    "http://localhost:5173",   # Vite dev (前端默认)
    "http://127.0.0.1:5173",
    "http://localhost:35000",  # 同源部署
    "http://127.0.0.1:35000",
]
_env_origins = os.environ.get("ALLOWED_ORIGINS", "").strip()
ALLOWED_ORIGINS = [o.strip() for o in _env_origins.split(",") if o.strip()] or _default_origins
CORS(app, origins=ALLOWED_ORIGINS, supports_credentials=True)

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
    # Sprint4: 注册模型注册表 API
    from model_registry import register_model_registry_routes
    register_model_registry_routes(app)
    # Sprint4: 注册 A/B 影子模式 API
    from shadow_predictor import register_shadow_routes, ensure_shadow_log_table
    ensure_shadow_log_table()
    register_shadow_routes(app)
    # Sprint4: 注册 ML 性能监控 API
    from ml_monitor import register_ml_monitor_routes, ensure_ml_metrics_table
    ensure_ml_metrics_table()
    register_ml_monitor_routes(app)
    # Sprint4: 注册 equity curve API
    from equity_curve import register_equity_curve_routes, ensure_equity_curve_table
    ensure_equity_curve_table()
    register_equity_curve_routes(app)
    # Sprint4: 注册 ML 可解释性 API
    from ml_explain import register_ml_explain_routes
    register_ml_explain_routes(app)
    # Sprint4: 注册 ML 校准 API
    from calibration_runtime import register_calibration_routes, ensure_calibration_table
    ensure_calibration_table()
    register_calibration_routes(app)
    # Sprint4: 注册策略对比 API
    from strategy_compare import register_strategy_compare_routes, ensure_strategy_compare_table
    ensure_strategy_compare_table()
    register_strategy_compare_routes(app)
    # Sprint5: 注册组合优化 API
    from portfolio_routes import register_portfolio_routes
    register_portfolio_routes(app)
    # Sprint5: 注册自动特征工程 API
    from auto_features import register_auto_features_routes
    register_auto_features_routes(app)
    # Sprint5: 注册敏感度扫描 API
    from sensitivity_scan import register_sensitivity_routes, ensure_sensitivity_table
    ensure_sensitivity_table()
    register_sensitivity_routes(app)
    # Sprint5: 注册多通道告警推送 API
    from alerting import register_alert_routes
    register_alert_routes(app)
    # Sprint5: 注册分布式缓存 API
    from cache_redis import register_cache_routes
    register_cache_routes(app)

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
        socketio.run(app, host='0.0.0.0', port=PORT, debug=DEBUG, allow_unsafe_werkzeug=True)
    else:
        app.run(host='0.0.0.0', port=PORT, debug=DEBUG)
