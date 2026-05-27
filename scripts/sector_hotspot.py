#!/usr/bin/env python3
"""板块热点自动挖掘 — 从强势板块中提取涨幅>5%的成分股推荐"""
import json, os, sys
from datetime import datetime
from urllib.request import urlopen, Request

API = os.environ.get('A_STOCK_API', 'http://127.0.0.1:35000')
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sector_data_cache.json')

# 补充缺失的成分股（系统缓存中不全的板块）
SUPPLEMENT_STOCKS = {
    'PCB': [
        {'code': '600183', 'name': '生益科技'},   # CCL覆铜板龙头，PCB上游核心
        {'code': '688183', 'name': '生益电子'},   # PCB制造
        {'code': '301628', 'name': '强达电路'},    # 高频高速PCB
        {'code': '300476', 'name': '胜宏科技'},    # HDI/高多层PCB
        {'code': '002579', 'name': '中京电子'},    # PCB制造
        {'code': '002916', 'name': '深南电路'},    # PCB龙头
    ],
    '玻璃基板': [
        {'code': '688559', 'name': '海目星'},
        {'code': '300395', 'name': '菲利华'},        
    ],
}

SECTOR_HOT_THRESHOLD = 5.0  # 涨幅>5%才推荐


def load_sector_stocks(sector_name: str) -> list:
    """加载板块成分股（缓存+补充）"""
    stocks = []
    
    # 从缓存读
    try:
        with open(CACHE, encoding='utf-8') as f:
            cache = json.load(f)
        sector = cache.get(sector_name, {})
        stocks = sector.get('stocks', [])
    except Exception:
        pass
    
    # 合并补充名单
    supplement = SUPPLEMENT_STOCKS.get(sector_name, [])
    existing_codes = {s['code'] for s in stocks}
    for s in supplement:
        if s['code'] not in existing_codes:
            stocks.append(s)
    
    return stocks


def get_hot_sectors() -> list:
    """获取今日强势板块（涨幅>1%或日报中明确推荐）"""
    try:
        req = Request(f'{API}/api/sectors/performance', headers={'User-Agent': 'hotspot/1.0'})
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        sectors = data.get('data', data.get('sectors', []))
        return [s for s in sectors if isinstance(s, dict) and s.get('change_pct', 0) > 1]
    except Exception:
        return []


def batch_fetch_prices(codes: list) -> dict:
    """批量拉取腾讯行情"""
    if not codes:
        return {}
    prefixes = {'00': 'sz', '30': 'sz', '60': 'sh', '68': 'sh'}
    qs = [f"{prefixes.get(c[:2],'sh')}{c}" for c in codes]
    
    # 分批50只
    results = {}
    for i in range(0, len(qs), 50):
        batch = qs[i:i+50]
        try:
            url = f"http://qt.gtimg.cn/q={','.join(batch)}"
            req = Request(url, headers={'User-Agent': 'hotspot/1.0'})
            with urlopen(req, timeout=10) as resp:
                text = resp.read().decode('gbk')
            for line in text.split(';'):
                if '~' not in line:
                    continue
                parts = line.split('~')
                if len(parts) < 40:
                    continue
                code = parts[2]
                results[code] = {
                    'name': parts[1],
                    'price': float(parts[3]),
                    'change_pct': (float(parts[3]) - float(parts[4])) / float(parts[4]) * 100,
                    'turnover': float(parts[38]),
                }
        except Exception:
            pass
    return results


def scan_sector_hotspots(sector_name: str) -> dict:
    """扫描板块内涨幅>5%的成分股"""
    stocks = load_sector_stocks(sector_name)
    if not stocks:
        return {'sector': sector_name, 'hot_stocks': [], 'error': '无成分股数据'}
    
    codes = [s['code'] for s in stocks]
    prices = batch_fetch_prices(codes)
    
    hot = []
    for s in stocks:
        code = s['code']
        if code not in prices:
            continue
        p = prices[code]
        if abs(p['change_pct']) >= SECTOR_HOT_THRESHOLD:
            hot.append({
                'code': code,
                'name': s['name'],
                'price': round(p['price'], 2),
                'change_pct': round(p['change_pct'], 2),
                'turnover': round(p['turnover'], 1),
            })
    
    hot.sort(key=lambda x: abs(x['change_pct']), reverse=True)
    return {
        'sector': sector_name,
        'hot_stocks': hot,
        'total_scanned': len(codes),
        'timestamp': datetime.now().isoformat(),
    }


def main():
    """主入口：扫描所有强势板块，输出推荐"""
    # 优先扫描日报中明确的热点板块
    report_sectors = ['PCB', '玻璃基板', '培育钻石', '贵金属', '人形机器人']
    
    all_results = []
    for sector in report_sectors:
        result = scan_sector_hotspots(sector)
        if result['hot_stocks']:
            all_results.append(result)
    
    if not all_results:
        sys.exit(0)
    
    lines = [f"🔥 板块热点扫描 ({datetime.now().strftime('%H:%M')})", "─" * 30]
    for r in all_results:
        lines.append(f"\n📌 {r['sector']}（扫描{r['total_scanned']}只）")
        for s in r['hot_stocks']:
            tag = '🚀' if s['change_pct'] > 8 else '📈' if s['change_pct'] > 0 else '💀'
            lines.append(f"  {tag} {s['name']}({s['code']}) {s['change_pct']:+.1f}% ¥{s['price']:.2f} 换手{s['turnover']:.1f}%")
    
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
