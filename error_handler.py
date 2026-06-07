"""
统一错误处理 + 标准化API响应助手
所有API端点应使用 api_success() 和 api_error() 保持响应格式一致
"""
from dataclasses import dataclass
from flask import jsonify


# ═══════════════════════════════════════════
# 标准化响应助手
# ═══════════════════════════════════════════

def api_success(data=None, **kwargs):
    """统一成功响应: {"success": true, "data": ..., ...}"""
    result = {"success": True}
    if data is not None:
        result["data"] = data
    result.update(kwargs)
    response = jsonify(result)
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    return response


def api_error(message: str, error_type: str = "internal_error",
              status_code: int = 500, detail: str = ""):
    """统一错误响应: {"success": false, "error": "...", "type": "..."}"""
    result = {
        "success": False,
        "error": message,
        "type": error_type,
    }
    if detail:
        result["detail"] = detail
    response = jsonify(result)
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    return response, status_code


def api_list_response(items: list, total: int, limit: int = None, offset: int = None):
    """统一列表响应 (含分页信息)"""
    result = {"success": True, "data": items, "total": total}
    if limit is not None:
        result["limit"] = limit
    if offset is not None:
        result["offset"] = offset
    response = jsonify(result)
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    return response


# ═══════════════════════════════════════════
# 异常类
# ═══════════════════════════════════════════

@dataclass
class AppError(Exception):
    """应用级异常，自动映射 HTTP 状态码"""
    message: str
    status_code: int = 500
    error_type: str = "internal_error"
    detail: str = ""


class NotFoundError(AppError):
    def __init__(self, resource: str, detail: str = ""):
        super().__init__(
            message=f"{resource} 不存在",
            status_code=404,
            error_type="not_found",
            detail=detail,
        )


class BadRequestError(AppError):
    def __init__(self, message: str, detail: str = ""):
        super().__init__(
            message=message,
            status_code=400,
            error_type="bad_request",
            detail=detail,
        )


class ExternalAPIError(AppError):
    def __init__(self, source: str, detail: str = ""):
        super().__init__(
            message=f"外部数据源 {source} 请求失败",
            status_code=502,
            error_type="external_api_error",
            detail=detail,
        )


class RateLimitError(AppError):
    def __init__(self, retry_after: int = 60):
        super().__init__(
            message=f"请求过于频繁，请{retry_after}秒后重试",
            status_code=429,
            error_type="rate_limited",
        )


class UnauthorizedError(AppError):
    def __init__(self, message: str = "未授权访问"):
        super().__init__(
            message=message,
            status_code=401,
            error_type="unauthorized",
        )


# ═══════════════════════════════════════════
# 全局错误处理器注册
# ═══════════════════════════════════════════

def register_error_handler(app):
    """注册全局错误处理器"""

    @app.errorhandler(AppError)
    def handle_app_error(error: AppError):
        return api_error(
            message=error.message,
            error_type=error.error_type,
            status_code=error.status_code,
            detail=error.detail,
        )

    @app.errorhandler(404)
    def handle_404(e):
        from flask import request, send_from_directory
        import logging
        logger = logging.getLogger(__name__)
        # Sprint6: SPA fallback - 非 /api/ 请求一律返回 index.html
        logger.info(f"404 hit: path={request.path} accept={request.headers.get('Accept', '')}")
        if not request.path.startswith("/api/"):
            try:
                import os
                # 优先用 api_server.py 中的 FRONTEND_DIR 路径
                try:
                    from api_server import FRONTEND_DIR
                except Exception:
                    FRONTEND_DIR = os.path.join(
                        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "stock_frontend", "dist")
                index_path = os.path.join(FRONTEND_DIR, "index.html")
                logger.info(f"SPA fallback: FRONTEND_DIR={FRONTEND_DIR} exists={os.path.isfile(index_path)}")
                if os.path.isfile(index_path):
                    return send_from_directory(FRONTEND_DIR, "index.html")
            except Exception as ex:
                logger.warning(f"SPA fallback err: {ex}")
        return api_error("路由不存在", "not_found", 404)

    @app.errorhandler(405)
    def handle_405(e):
        return api_error("不支持的请求方法", "method_not_allowed", 405)

    @app.errorhandler(500)
    def handle_500(e):
        return api_error("服务器内部错误", "internal_error", 500, detail=str(e))


# ═══════════════════════════════════════════
# 统一响应装饰器 (修复 ARCH-02: 端点迁移到统一格式)
# ═══════════════════════════════════════════

from functools import wraps
import logging as _logging

_json_endpoint_logger = _logging.getLogger(__name__)


def json_endpoint(schema: str = "success", rate_limit_name: str = None):
    """统一响应格式装饰器(渐进式迁移用)

    用法:
        @json_endpoint("success")
        def my_endpoint():
            return {"key": "value"}   # 自动包成 {"success": true, "data": {...}}

        @json_endpoint("list")
        def list_endpoint():
            return [{"a": 1}, {"a": 2}]   # 自动包成 {"success": true, "data": [...], "total": 2}

        @json_endpoint("error", rate_limit_name="debate_start")
        def error_endpoint():
            raise BadRequestError("invalid input")

    schema 选项:
        - "success": 返回 dict 包装为 {success, data}
        - "list":    返回 list 包装为 {success, data, total}
        - "raw":     原样返回 (用于已标准化的端点)
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                result = f(*args, **kwargs)
            except AppError as e:
                return api_error(
                    message=e.message,
                    error_type=e.error_type,
                    status_code=e.status_code,
                    detail=e.detail,
                )
            except Exception as e:
                _json_endpoint_logger.error(f"Endpoint {f.__name__} unhandled: {e}", exc_info=True)
                return api_error(
                    message=f"处理失败: {type(e).__name__}",
                    error_type="internal_error",
                    status_code=500,
                    detail=str(e),
                )
            # 已是 Response 对象,直接返回
            if hasattr(result, "headers") and hasattr(result, "status_code"):
                return result
            if schema == "list":
                if isinstance(result, tuple) and len(result) == 2:
                    items, total = result
                    return api_list_response(items, total)
                if isinstance(result, list):
                    return api_list_response(result, len(result))
                return api_success(result)
            if schema == "raw":
                return result
            # 默认 success
            return api_success(result)
        return wrapper
    return decorator
