"""
AI 密钥管理 — 环境变量优先，DB 兜底
"""
import os

# Provider → 环境变量映射
PROVIDER_ENV_MAP = {
    "openai": "OPENAI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "qwen": "QWEN_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "grok": "GROK_API_KEY",
}


def get_api_key(provider: str, db_key: str = "") -> str:
    """
    获取 AI 密钥：环境变量 > DB 存储 > Config表 > 空字符串

    Args:
        provider: AI provider 名称 (openai/deepseek/qwen/gemini/grok)
        db_key: 数据库中存储的密钥（兜底）
    """
    env_var = PROVIDER_ENV_MAP.get(provider.lower(), "")
    if env_var and os.environ.get(env_var):
        return os.environ[env_var]
    if db_key:
        return db_key

    # Last resort: check Config table
    try:
        from models import SessionLocal, Config
        db = SessionLocal()
        try:
            row = db.query(Config).filter(Config.key == f'{provider}_api_key').first()
            if row and row.value:
                return row.value
        finally:
            db.close()
    except Exception:
        pass

    return ""


def has_env_key(provider: str) -> bool:
    """检查是否已配置环境变量密钥"""
    env_var = PROVIDER_ENV_MAP.get(provider.lower(), "")
    return bool(env_var and os.environ.get(env_var))
