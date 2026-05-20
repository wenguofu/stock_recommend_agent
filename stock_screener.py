#!/usr/bin/env python3
"""股票筛选推荐引擎
策略化扫描A股，生成每日/每周推荐清单
"""
import json
import urllib.request
import time
from datetime import datetime, date
from typing import List, Dict, Optional

PROJECT_DIR = '/Users/wgfu/work/a-stock-trading'

# 策略定义
STRATEGIES = {
    'youzi': {
        'name': '游资策略',
        'desc': '高换手、强动量、概念驱动型短线机会',
        'sectors': ['半导体', '人工智能', '新能源汽车', '军工', '低空经济', '机器人'],
    },
    'lianghua': {
        'name': '量化策略',
        'desc': '技术指标驱动的中期趋势机会（MACD金叉、放量突破、RSI适中）',
        'sectors': ['全部A股'],
    },
    'jichang': {
        'name': '基础工具',
        'desc': '基本面+技术面双重验证的稳健型机会',
        'sectors': ['全部A股'],
    },
}

def load_sector_stocks(sector_names: List[str] = None, max_count: int = 300) -> List[Dict]:
    """从缓存加载指定板块的股票列表"""
    with open(f'{PROJECT_DIR}/sector_data_cache.json', 'r') as f:
        data = json.load(f)
    
    stocks = []
    if not sector_names or '全部A股' in sector_names:
        # 加载全部 — 取前max_count只（避免全A股5000+导致超时）
        if '全部A股' in data:
            all_stocks = data['全部A股']['stocks']
            stocks.extend(all_stocks[:max_count])
    else:
        for name in sector_names:
            if name in data:
                stocks.extend(data[name]['stocks'])
    
    # 去重
    seen = set()
    unique = []
    for s in stocks:
        if s['code'] not in seen:
            seen.add(s['code'])
            unique.append(s)
    return unique

def batch_fetch_quotes(codes: List[str]) -> Dict[str, Dict]:
    """批量获取实时行情，新浪支持最多约80个一次"""
    results = {}
    # 一次性全部查询（新浪支持多code逗号分隔）
    suffix_parts = []
    for c in codes:
        c = c.strip()
        if c.startswith(('5', '6', '9')):
            suffix_parts.append(f"sh{c}")
        else:
            suffix_parts.append(f"sz{c}")
    
    # 分批，每批50个
    batch_size = 50
    for i in range(0, len(suffix_parts), batch_size):
        batch = suffix_parts[i:i+batch_size]
        url = f"http://qt.gtimg.cn/q={','.join(batch)}"
        try:
            req = urllib.request.urlopen(url, timeout=10)
            raw = req.read().decode('gbk')
            for line in raw.strip().split(';'):
                if not line.strip():
                    continue
                try:
                    parts = line.split('~')
                    if len(parts) < 40:
                        continue
                    code = parts[2].strip()
                    results[code] = {
                        'code': code,
                        'name': parts[1].strip(),
                        'price': float(parts[3]),
                        'yclose': float(parts[4]),
                        'open': float(parts[5]),
                        'volume': int(parts[6]) if parts[6] else 0,
                        'amount': float(parts[37]) if parts[37] else 0,  # 成交额
                        'high': float(parts[33]) if parts[33] else 0,
                        'low': float(parts[34]) if parts[34] else 0,
                        'change_pct': float(parts[32]) if parts[32] else 0,  # 涨跌幅%
                        'turnover': float(parts[38]) if len(parts) > 38 and parts[38] else 0,  # 换手率%
                        'pe': float(parts[39]) if len(parts) > 39 and parts[39] else 0,
                    }
                except (ValueError, IndexError):
                    continue
        except Exception as e:
            print(f"[警告] 批量获取行情失败 batch {i}: {e}")
        
        time.sleep(0.3)  # 避免封IP
    
    return results

def calculate_score(quote: Dict, strategy: str) -> float:
    """根据策略计算股票评分"""
    score = 0.0
    change = abs(quote.get('change_pct', 0))
    turnover = quote.get('turnover', 0)
    volume = quote.get('volume', 0)
    price = quote.get('price', 0)
    yclose = quote.get('yclose', 0)
    
    if strategy == 'youzi':
        # 游资策略：高换手、强动量、大幅波动
        if change >= 5: score += 30  # 大涨加分
        elif change >= 3: score += 20
        elif change >= 1: score += 10
        
        if turnover >= 10: score += 25  # 高换手加分
        elif turnover >= 5: score += 15
        elif turnover >= 3: score += 8
        
        if price > yclose: score += 10  # 上涨加分
        if volume > 0: score += 5
        
        # 涨停候选（9.5%以上且换手率高）
        if change >= 9.5 and turnover >= 5:
            score += 20
        
        # 涨跌幅适中（排除无量涨停和跌停）
        if change < 1 or change > 10:
            score -= 5
    
    elif strategy == 'lianghua':
        # 量化策略：技术指标型
        if 1 <= change <= 5: score += 20  # 温和上涨
        if 3 <= turnover <= 15: score += 15  # 适中换手
        if price > yclose: score += 10
        
        # 放量（如果昨收存在且成交量适中）
        if volume > 0: score += 5
        
        if change >= 0 and turnover >= 2: score += 10
    
    elif strategy == 'jichang':
        # 基础工具策略：稳健型
        if 0 < change <= 5: score += 20
        if 2 <= turnover <= 10: score += 15
        if price > yclose: score += 10
        if volume > 0: score += 5
        
        # 低PE加分
        pe = quote.get('pe', 0)
        if 0 < pe < 50: score += 10
    
    return score

def screen_stocks(strategy: str, top_n: int = 10) -> List[Dict]:
    """执行股票筛选"""
    strategy_config = STRATEGIES.get(strategy)
    if not strategy_config:
        raise ValueError(f"未知策略: {strategy}")
    
    # 1. 加载候选股票池
    stocks = load_sector_stocks(strategy_config['sectors'])
    print(f"[筛选] {strategy} 候选池: {len(stocks)} 只")
    
    # 2. 批量获取行情
    codes = [s['code'] for s in stocks]
    quotes = batch_fetch_quotes(codes)
    print(f"[筛选] 获取行情: {len(quotes)} 只")
    
    # 3. 评分
    scored = []
    for code, q in quotes.items():
        if q['price'] <= 0 or q['price'] < 2:  # 过滤停牌和低价股
            continue
        score = calculate_score(q, strategy)
        if score > 0:
            scored.append({**q, 'score': round(score, 1)})
    
    # 4. 排序取前N
    scored.sort(key=lambda x: x['score'], reverse=True)
    top = scored[:top_n]
    
    # 5. 格式化输出
    result = []
    for idx, s in enumerate(top, 1):
        result.append({
            'rank': idx,
            'code': s['code'],
            'name': s['name'],
            'price': s['price'],
            'change_pct': s['change_pct'],
            'turnover': s['turnover'],
            'score': s['score'],
            'reason': _generate_reason(s, strategy),
        })
    
    return result

def _generate_reason(quote: Dict, strategy: str) -> str:
    """生成推荐理由"""
    parts = []
    cp = quote.get('change_pct', 0)
    to = quote.get('turnover', 0)
    
    if cp >= 9.5:
        parts.append(f"强势涨停(+{cp:.1f}%)")
    elif cp >= 5:
        parts.append(f"大涨+{cp:.1f}%")
    elif cp >= 3:
        parts.append(f"上涨+{cp:.1f}%")
    elif cp >= 1:
        parts.append(f"小幅上涨+{cp:.1f}%")
    
    if to >= 15:
        parts.append(f"换手率极高{to:.1f}%")
    elif to >= 8:
        parts.append(f"换手活跃{to:.1f}%")
    elif to >= 3:
        parts.append(f"换手适中{to:.1f}%")
    
    if strategy == 'youzi' and cp >= 9.5 and to >= 5:
        parts.append("游资关注标的")
    elif strategy == 'lianghua' and 1 <= cp <= 5 and 3 <= to <= 15:
        parts.append("量价配合良好，技术面偏多")
    elif strategy == 'jichang' and 0 < cp <= 5:
        parts.append("稳健上涨，基本面支撑")
    
    return '，'.join(parts) if parts else '技术面关注'

def generate_recommendations(strategies: List[str] = None, top_n: int = 10) -> Dict:
    """生成推荐清单（支持多策略）"""
    if not strategies:
        strategies = list(STRATEGIES.keys())
    
    result = {}
    total_stocks = []
    
    for s in strategies:
        picks = screen_stocks(s, top_n=top_n)
        result[s] = {
            'strategy_name': STRATEGIES[s]['name'],
            'strategy_desc': STRATEGIES[s]['desc'],
            'picks': picks,
            'generated_at': datetime.now().isoformat(),
        }
        total_stocks.extend([p['code'] for p in picks])
    
    return {
        'strategies': result,
        'total_unique': len(set(total_stocks)),
        'generated_at': datetime.now().isoformat(),
        'date': date.today().isoformat(),
    }

if __name__ == '__main__':
    import sys
    strategies = sys.argv[1:] if len(sys.argv) > 1 else None
    result = generate_recommendations(strategies, top_n=10)
    
    print(f"=== 股票推荐 ({result['date']}) ===")
    print(f"覆盖策略: {len(result['strategies'])}个")
    print(f"推荐股票: {result['total_unique']}只\n")
    
    for sname, sdata in result['strategies'].items():
        print(f"--- {sdata['strategy_name']} ---")
        for p in sdata['picks']:
            print(f"  #{p['rank']} {p['code']} {p['name']} "
                  f"价格{p['price']:.2f} "
                  f"{'+' if p['change_pct']>=0 else ''}{p['change_pct']:.1f}% "
                  f"换手{p['turnover']:.1f}% "
                  f"评分{p['score']}")
            print(f"    理由: {p['reason']}")
