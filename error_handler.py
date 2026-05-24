"""
统一错误处理 — 所有 API 返回一致 JSON 格式
"""
from dataclasses import dataclass, asdict
from flask import jsonify


@dataclass
class AppError(Exception):
    """应用级异常，自动映射 HTTP 状态码"""
    message: str
    status_code: int = 500
    error_type: str = "internal_error"
    detail: str = ""


# ── 预定义错误 ──

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


def register_error_handler(app):
    """注册全局错误处理器"""

    @app.errorhandler(AppError)
    def handle_app_error(error: AppError):
        return jsonify({
            "error": True,
            "type": error.error_type,
            "message": error.message,
            "detail": error.detail,
        }), error.status_code

    @app.errorhandler(404)
    def handle_404(e):
        return jsonify({
            "error": True,
            "type": "not_found",
            "message": "路由不存在",
        }), 404

    @app.errorhandler(500)
    def handle_500(e):
        return jsonify({
            "error": True,
            "type": "internal_error",
            "message": "服务器内部错误",
            "detail": str(e),
        }), 500
