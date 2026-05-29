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
        return api_error("路由不存在", "not_found", 404)

    @app.errorhandler(405)
    def handle_405(e):
        return api_error("不支持的请求方法", "method_not_allowed", 405)

    @app.errorhandler(500)
    def handle_500(e):
        return api_error("服务器内部错误", "internal_error", 500, detail=str(e))
