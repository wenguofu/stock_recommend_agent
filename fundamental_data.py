#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""基本面数据模块 - 使用AKShare获取东方财富财务数据"""

import traceback

# AKShare 财务指标中文名 → 内部字段映射
KEY_MAP = {
    '营业总收入': 'revenue',
    '归母净利润': 'net_profit',
    '营业收入': 'revenue',
    '基本每股收益': 'eps',
    '每股收益': 'eps',
    '净资产收益率(ROE)': 'roe',
    'ROE': 'roe',
    '毛利率': 'gross_margin',
    '销售净利率': 'net_margin',
    '经营现金流量净额': 'operating_cf',
    '股东权益合计(净资产)': 'equity',
}


def fetch_financials(code):
    """使用AKShare获取财务数据"""
    try:
        import akshare as ak
        df = ak.stock_financial_abstract(symbol=code)
        if df is None or df.empty:
            return None

        # 提取日期列（所有以数字开头的列，如 20260331）
        date_cols = [c for c in df.columns if c.replace('-', '').isdigit()]
        if not date_cols:
            return None
        
        # 最新日期
        latest_date = sorted(date_cols, reverse=True)[0]
        
        # 解析数据
        result = {
            'code': code,
            'report_date': latest_date[:4] + '-' + latest_date[4:6] + '-' + latest_date[6:8] if len(latest_date) == 8 else latest_date,
            'report_type': '年报' if latest_date[4:6] == '12' else ('中报' if latest_date[4:6] == '06' else ('一季报' if latest_date[4:6] == '03' else '三季报')),
        }

        # 提取最新一期和前三期的数据
        period_dates = sorted(date_cols, reverse=True)[:8]
        periods = []
        for d in period_dates:
            rd = d[:4] + '-' + d[4:6] + '-' + d[6:8] if len(d) == 8 else d
            rt = '年报' if d[4:6] == '12' else ('中报' if d[4:6] == '06' else ('一季报' if d[4:6] == '03' else '三季报'))
            pdict = {'report_date': rd, 'report_type': rt}
            periods.append(pdict)
        
        result['periods'] = periods
        
        # 遍历每一行，提取指标值
        for _, row in df.iterrows():
            indicator_name = str(row.get('指标', '')).strip()
            eng_key = KEY_MAP.get(indicator_name)
            if eng_key is None:
                continue
            
            # 取最新一期
            val = row.get(latest_date)
            if val is not None and val != '':
                try:
                    result[eng_key] = float(val)
                except (ValueError, TypeError):
                    pass
            
            # 填充到各 period
            for i, d in enumerate(period_dates):
                if i < len(result['periods']):
                    v = row.get(d)
                    if v is not None and v != '':
                        try:
                            result['periods'][i][eng_key] = float(v)
                        except (ValueError, TypeError):
                            pass

        # 判断是否有数据
        if 'revenue' not in result and 'net_profit' not in result:
            return None
            
        return result
    except Exception as e:
        print(f"[Fundamental] fetch_financials failed for {code}: {e}")
        traceback.print_exc()
        return None


def get_valuation(code):
    """获取估值数据 PE/PB"""
    try:
        import akshare as ak
        df = ak.stock_financial_analysis_indicator(symbol=code)
        if df is None or df.empty:
            return None
        
        date_cols = [c for c in df.columns if c.replace('-', '').isdigit()]
        if not date_cols:
            return None
        
        latest_date = sorted(date_cols, reverse=True)[0]
        result = {}
        
        for _, row in df.iterrows():
            name = str(row.get('指标', '')).strip()
            val = row.get(latest_date)
            if val is not None and val != '':
                try:
                    if '市盈率' in name and 'pe' not in result:
                        result['pe_ttm'] = float(val)
                    elif '市净率' in name and 'pb' not in result:
                        result['pb'] = float(val)
                except (ValueError, TypeError):
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
