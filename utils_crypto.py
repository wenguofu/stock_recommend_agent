#!/usr/bin/env python3
"""加密工具 - 用于敏感信息加密存储"""
import base64
import hashlib
from cryptography.fernet import Fernet
from typing import Optional

# 从环境变量或配置文件获取密钥
def _get_encryption_key() -> bytes:
    """获取加密密钥"""
    import os
    # 使用固定盐值和机器相关信息生成密钥
    # 实际生产环境建议使用更安全的方式存储密钥
    salt = b"a_stock_trading_salt_v1"
    machine_id = f"{os.getenv('HOSTNAME', 'localhost')}_{os.getenv('USER', 'user')}"
    key_material = hashlib.pbkdf2_hmac('sha256', machine_id.encode(), salt, 100000)
    return base64.urlsafe_b64encode(key_material[:32])

_fernet: Optional[Fernet] = None

def get_fernet() -> Fernet:
    """获取Fernet加密实例"""
    global _fernet
    if _fernet is None:
        key = _get_encryption_key()
        _fernet = Fernet(key)
    return _fernet

def encrypt_token(token: str) -> str:
    """加密敏感token"""
    f = get_fernet()
    encrypted = f.encrypt(token.encode())
    return base64.urlsafe_b64encode(encrypted).decode()

def decrypt_token(encrypted_token: str) -> str:
    """解密token"""
    f = get_fernet()
    encrypted = base64.urlsafe_b64decode(encrypted_token.encode())
    return f.decrypt(encrypted).decode()

def get_tushare_token() -> str:
    """从数据库获取解密的tushare token"""
    from models import SessionLocal
    from db import get_config
    db = SessionLocal()
    try:
        encrypted = get_config(db, 'tushare_token')
        if encrypted:
            return decrypt_token(encrypted)
    finally:
        db.close()
    return None

def save_tushare_token(token: str):
    """加密并保存tushare token到数据库"""
    from models import SessionLocal
    from db import set_config
    db = SessionLocal()
    try:
        encrypted = encrypt_token(token)
        set_config(db, 'tushare_token', encrypted)
    finally:
        db.close()
