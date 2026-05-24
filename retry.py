"""
外部 API 重试装饰器 — 腾讯/Sina/akshare 调用自动重试
"""
import time
import functools
import logging

logger = logging.getLogger(__name__)


def retry_on_failure(max_attempts=3, backoff=2.0, exceptions=(Exception,)):
    """
    装饰器：失败自动重试，指数退避

    Args:
        max_attempts: 最大尝试次数（含首次）
        backoff: 退避倍数（延迟 = backoff ^ attempt）
        exceptions: 捕获的异常类型
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt < max_attempts:
                        delay = backoff ** attempt
                        logger.warning(
                            f"重试 {func.__name__} (第{attempt}/{max_attempts}次失败): {e}，"
                            f"{delay:.1f}s 后重试"
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"重试 {func.__name__} 全部 {max_attempts} 次失败: {e}"
                        )
            raise last_exc
        return wrapper
    return decorator
