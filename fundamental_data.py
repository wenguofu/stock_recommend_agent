#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""基本面数据模块 - 使用AKShare获取东方财富财务数据"""

import traceback

# THS字段名 → 内部字段映射
THS_KEY_MAP = {
    '营业总收入': 'revenue',
    '净利润': 'net_profit',
    '基本每股收益': 'eps',
    '销售毛利率': 'gross_margin',
    '销售净利率': 'net_margin',
    '净资产收益率': 'roe',
    '每股经营现金流': 'operating_cf',
    '每股净资产': 'equity',
}


def _parse_ths_value(val_str):
    """解析THS返回值: '12.36亿' → 1236000000, '20.50%' → 20.50, '2.0500' → 2.05"""
    import math
    if val_str is None or val_str == '':
        return None
    if isinstance(val_str, float) and math.isnan(val_str):
        return None
    s = str(val_str).strip()
    if s == 'False' or s == '':
        return None
    try:
        num = float(s.replace('亿', '').replace('%', '').replace(',', ''))
        if '亿' in s:
            num *= 1e8
        return num
    except (ValueError, TypeError):
        return None


def fetch_financials(code):
    """使用AKShare(同花顺)获取财务数据 — Sina接口不稳定故改用THS"""
    try:
        import akshare as ak
        import pandas as pd

        # 先尝试年报数据，没有则用报告期
        df = None
        for indicator in ['按年度', '按报告期']:
            try:
                df = ak.stock_financial_abstract_ths(symbol=code, indicator=indicator)
                if df is not None and not df.empty:
                    break
            except Exception:
                continue

        if df is None or df.empty:
            return None

        # 按报告期排序，取最新一条
        df = df.sort_values('报告期', ascending=False).reset_index(drop=True)

        latest = df.iloc[0]
        report_date_raw = str(latest['报告期'])[:10]  # '2011-12-31' or '2011'
        result = {
            'code': code,
        }

        # 解析report_date
        if '-' in report_date_raw:
            result['report_date'] = report_date_raw
            m = report_date_raw[5:7]
        else:
            # 年度格式 '2011'
            result['report_date'] = report_date_raw + '-12-31'
            m = '12'

        result['report_type'] = {
            '12': '年报', '06': '中报', '03': '一季报', '09': '三季报'
        }.get(m, '年报')

        # 提取最新一期指标
        for ths_name, eng_key in THS_KEY_MAP.items():
            val = _parse_ths_value(latest.get(ths_name))
            if val is not None:
                result[eng_key] = val

        # 提取多期数据（最近8期）
        periods = []
        for _, row in df.head(8).iterrows():
            rd = str(row['报告期'])[:10]
            if '-' not in rd:
                rd = rd + '-12-31'
            m = rd[5:7]
            rt = {'12': '年报', '06': '中报', '03': '一季报', '09': '三季报'}.get(m, '年报')
            pdict = {'report_date': rd, 'report_type': rt}
            for ths_name, eng_key in THS_KEY_MAP.items():
                v = _parse_ths_value(row.get(ths_name))
                if v is not None:
                    pdict[eng_key] = v
            periods.append(pdict)

        result['periods'] = periods

        if 'revenue' not in result and 'net_profit' not in result:
            return None

        return result
    except Exception as e:
        print(f"[Fundamental] fetch_financials failed for {code}: {e}")
        traceback.print_exc()
        return None


def get_valuation(code):
    """获取估值数据 PE/PB — 使用 Baidu PB（PE需交易时段从实时行情获取）"""
    try:
        import akshare as ak
        result = {}

        # 1. 从 Baidu 获取 PB（已验证稳定可用）
        try:
            pb_df = ak.stock_zh_valuation_baidu(symbol=code, indicator='市净率')
            if pb_df is not None and not pb_df.empty:
                latest_pb = pb_df['value'].iloc[-1]
                result['pb'] = float(latest_pb)
        except Exception:
            pass

        return result if result else None
    except Exception as e:
        print(f"[Fundamental] get_valuation failed for {code}: {e}")
        return None


def fetch_and_cache(code, db=None):
    """获取并缓存基本面数据，有db则写入数据库"""
    fin = fetch_financials(code)
    val = get_valuation(code)

    data = fin or {}
    if val:
        if val.get('pe_ttm') and not data.get('pe_ttm'):
            data['pe_ttm'] = val['pe_ttm']
        if val.get('pb') and not data.get('pb'):
            data['pb'] = val['pb']

    # 写入数据库
    if db and data:
        try:
            from db import save_stock_financial
            save_stock_financial(db, data)
        except Exception as e:
            print(f"[Fundamental] save to DB failed: {e}")

    return data


def get_fundamental_data_for_ai(code, db=None):
    """返回格式化的基本面文本，用于AI prompt注入"""
    data = None

    # 先从数据库读
    if db:
        try:
            from db import get_latest_financial
            data = get_latest_financial(db, code)
        except Exception:
            pass

    # 数据库没有则实时获取
    if not data:
        data = fetch_and_cache(code, db)

    if not data:
        return "【基本面数据】暂无\n"

    lines = [
        f"【基本面数据】股票代码: {code}",
        f"报告期: {data.get('report_date', 'N/A')} ({data.get('report_type', 'N/A')})",
    ]

    has_data = False
    fields_display = [
        ('revenue', '营业收入(亿)'),
        ('net_profit', '净利润(亿)'),
        ('gross_margin', '毛利率(%)'),
        ('net_margin', '净利率(%)'),
        ('eps', '每股收益'),
        ('roe', '净资产收益率(%)'),
        ('operating_cf', '经营现金流(亿)'),
        ('equity', '净资产(亿)'),
        ('pe_ttm', '市盈率TTM'),
        ('pb', '市净率'),
    ]
    for key, label in fields_display:
        val = data.get(key)
        if val is not None:
            # 金额类字段转换单位为亿
            if key in ('revenue', 'net_profit', 'operating_cf', 'equity'):
                # AKShare返回的是原始金额（元），转为亿
                if abs(val) > 1e8:
                    val_display = val / 1e8
                elif abs(val) > 1e4:
                    val_display = val / 1e4
                else:
                    val_display = val
                lines.append(f"  {label}: {val_display:.2f}")
            else:
                lines.append(f"  {label}: {val:.2f}")
            has_data = True

    if not has_data:
        return "【基本面数据】暂无\n"

    # 多期趋势
    periods = data.get('periods', [])
    if len(periods) >= 2:
        lines.append("")
        lines.append(f"  多期趋势(最近{len(periods)}期):")
        for p in periods:
            rev = p.get('revenue', '')
            prof = p.get('net_profit', '')
            if isinstance(rev, (int, float)):
                rev_s = f"{rev/1e8:.2f}亿" if abs(rev) > 1e8 else f"{rev:.2f}"
            else:
                rev_s = 'N/A'
            if isinstance(prof, (int, float)):
                prof_s = f"{prof/1e8:.2f}亿" if abs(prof) > 1e8 else f"{prof:.2f}"
            else:
                prof_s = 'N/A'
            lines.append(f"    {p.get('report_date','?')}: 营收={rev_s} 净利={prof_s}")

    return "\n".join(lines) + "\n"


if __name__ == '__main__':
    import sys
    code = sys.argv[1] if len(sys.argv) > 1 else '300433'
    print(f"=== {code} 财务数据 ===")
    data = fetch_financials(code)
    if data:
        for k, v in data.items():
            if k == 'periods':
                print(f"  多期记录: {len(v)} 期")
                for p in v[:4]:
                    rev = p.get('revenue', 0)
                    net = p.get('net_profit', 0)
                    print(f"    {p.get('report_date','?')}: rev={rev/1e8:.2f}亿 net={net/1e8:.2f}亿")
            else:
                if isinstance(v, (int, float)) and abs(v) > 1e8:
                    print(f"  {k}: {v/1e8:.2f}亿")
                else:
                    print(f"  {k}: {v}")
    
    print(f"\n=== {code} 估值数据 ===")
    val = get_valuation(code)
    if val:
        for k, v in val.items():
            print(f"  {k}: {v}")
    
    print(f"\n=== AI格式化文本 ===")
    print(get_fundamental_data_for_ai(code))
