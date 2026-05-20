#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
工具函数模块
"""

import re


def is_us_stock(code):
    """判断是否为美股代码（纯字母，2-5位）"""
    code_str = str(code).strip()
    return bool(re.match(r'^[A-Za-z]{1,5}$', code_str))


def is_a_stock(code):
    """判断是否为A股代码（6位数字）"""
    code_str = str(code).strip()
    return bool(re.match(r'^\d{6}$', code_str))


def get_stock_code_format(code):
    """转换股票代码格式（用于新浪API）"""
    code_str = str(code).strip()
    
    # 美股指数（带$前缀）
    if code_str.startswith('$') or code_str in ['$dji', '$inx', '$ixic', '$comp']:
        if not code_str.startswith('$'):
            return f"gb_${code_str}"
        return f"gb_{code_str}"
    
    # 美股：gb_前缀
    if re.match(r'^[A-Za-z]{1,5}$', code_str):
        return f"gb_{code_str.lower()}"
    
    # 如果已经是sh/sz/gb格式，直接返回
    if code_str.startswith(('sh', 'sz', 'gb_')):
        return code_str
    
    # 处理指数代码
    if code_str == '1A0001' or code_str == '000001':
        return 'sh000001'
    elif code_str.startswith('1A'):
        return f"sh{code_str[2:]}"
    elif code_str.startswith('6'):
        return f"sh{code_str}"
    elif code_str.startswith(('0', '3')):
        return f"sz{code_str}"
    else:
        return code_str


def get_secid(code):
    """获取东方财富API的secid格式"""
    code_str = str(code).strip()
    
    # 美股
    if re.match(r'^[A-Za-z]{1,5}$', code_str):
        return f"100.{code_str.upper()}"
    
    # 处理指数代码
    if code_str == '1A0001' or code_str == '000001':
        return '1.000001'
    elif code_str.startswith('1A'):
        return f"1.{code_str[2:]}"
    elif code_str.startswith('6'):
        return f"1.{code_str}"
    else:
        return f"0.{code_str}"


def is_valid_stock_code(code):
    """通用股票代码校验：6位A股或1-5位美股ticker或美股指数"""
    code_str = str(code).strip()
    if re.match(r'^\d{6}$', code_str):
        return True
    if re.match(r'^\$[a-zA-Z]{2,5}$', code_str):
        return True
    if re.match(r'^[A-Za-z]{1,5}$', code_str):
        return True
    return False
