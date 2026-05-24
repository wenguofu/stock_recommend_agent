"""
结构化日志配置 — 统一 JSON 格式输出
"""
import logging
import sys
from datetime import datetime


class JsonFormatter(logging.Formatter):
    """JSON 格式日志，方便 grep/jq 分析"""

    def format(self, record):
        import json
        return json.dumps({
            "ts": datetime.now().isoformat(),
            "level": record.levelname,
            "module": record.name,
            "msg": record.getMessage(),
        }, ensure_ascii=False, default=str)


def setup_logging(level=logging.INFO):
    """初始化全局日志配置"""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.setLevel(level)
    # 清除已有 handler 避免重复
    root.handlers = [h for h in root.handlers if not isinstance(h, logging.StreamHandler)]
    root.addHandler(handler)

    # 抑制 Flask/Werkzeug 的默认日志格式
    logging.getLogger("werkzeug").handlers = []

    return root
