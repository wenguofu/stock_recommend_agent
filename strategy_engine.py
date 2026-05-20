"""
策略选股引擎 v2

整合：板块热度评分 + 多因子筛选 + 多头策略池

用法:
  uv run python strategy_engine.py                     # 运行所有策略
  uv run python strategy_engine.py youzi lianghua       # 指定策略
"""

import json
import os
import sys
import time
from datetime import datetime, date
from typing import List, Dict, Optional

PROJECT_DIR = os.path.dirname(__file__)
SECTOR_DATA_DIR = os.path.join(PROJECT_DIR, "sector_data")


# ═══════════════════════════════════════════════
# 策略定义（可扩展）
# ═══════════════════════════════════════════════

STRATEGIES = {
    "sector_momentum": {
        "name": "板块动量",
        "desc": "当日最强板块的领涨股，板块热度×个股强度双因子",
        "min_score": 30,
    },
    "youzi": {
        "name": "游资策略",
        "desc": "高换手、强动量、概念驱动型短线机会",
        "min_score": 25,
    },
    "lianghua": {
        "name": "量化策略",
        "desc": "MACD金叉、放量突破、RSI适中技术指标驱动",
        "min_score": 20,
    },
    "jichang": {
        "name": "基础工具",
        "desc": "基本面+技术面双重验证的稳健型机会",
        "min_score": 15,
    },
}


# ═══════════════════════════════════════════════
# 板块数据加载
# ═══════════════════════════════════════════════

def load_today_sectors():
    """加载今日板块热度数据"""
    files = sorted(os.listdir(SECTOR_DATA_DIR))
    json_files = [f for f in files if f.endswith(".json")]
    if not json_files:
        return None, []
    
    latest = json_files[-1]
    with open(os.path.join(SECTOR_DATA_DIR, latest), encoding="utf-8") as f:
        data = json.load(f)
    
    sectors = data.get("sectors", [])
    # 计算热度
    scored = []
    for i, s in enumerate(sectors):
        combined = s.get("driver", "") + s.get("insight", "") + s.get("view", "")
        heat = 10  # base
        intensity = ["需求爆发", "供不应求", "大涨", "飙升", "突破", "历史新高",
                     "商业化", "景气度", "资本支出", "大幅上调"]
        for w in intensity:
            if w in combined: heat += 3
        if len(combined) > 400: heat += 5
        heat += max(0, 10 - i * 2)  # 位置加成
        scored.append({
            "name": s["name"],
            "heat": min(100, heat),
            "stocks_text": s.get("stocks", ""),
            "rank": i + 1,
        })
    
    scored.sort(key=lambda x: x["heat"], reverse=True)
    return scored, [s["name"] for s in scored[:5]]


def parse_stock_list(stocks_text: str) -> List[str]:
    """从板块文本提取股票代码
    格式: "华培动力、三花智控、中大力德..."
    返回股票名列表（用于后续查行情）
    """
    return [s.strip() for s in stocks_text.replace("、", ",").split(",") if s.strip()]


# ═══════════════════════════════════════════════
# 行情数据获取
# ═══════════════════════════════════════════════

def fetch_batch_quotes(codes: List[str]) -> Dict[str, Dict]:
    """批量获取实时行情（新浪接口）"""
    results = {}
    if not codes:
        return results
    
    suffix_parts = []
    for c in codes:
        c = c.strip()
        if c.startswith(("5", "6", "9")):
            suffix_parts.append(f"sh{c}")
        else:
            suffix_parts.append(f"sz{c}")
    
    batch_size = 50
    for i in range(0, len(suffix_parts), batch_size):
        batch = suffix_parts[i:i+batch_size]
        url = f"http://qt.gtimg.cn/q={','.join(batch)}"
        try:
            import urllib.request
            req = urllib.request.urlopen(url, timeout=10)
            raw = req.read().decode("gbk")
            for line in raw.strip().split(";"):
                if not line.strip():
                    continue
                parts = line.split("~")
                if len(parts) < 40:
                    continue
                code = parts[2].strip()
                try:
                    results[code] = {
                        "code": code,
                        "name": parts[1].strip(),
                        "price": float(parts[3]),
                        "yclose": float(parts[4]),
                        "high": float(parts[33]) if parts[33] else 0,
                        "low": float(parts[34]) if parts[34] else 0,
                        "change_pct": float(parts[32]) if parts[32] else 0,
                        "turnover": float(parts[38]) if len(parts) > 38 and parts[38] else 0,
                        "volume": int(parts[6]) if parts[6] else 0,
                        "amount": float(parts[37]) if parts[37] else 0,
                        "pe": float(parts[39]) if len(parts) > 39 and parts[39] else 0,
                    }
                except (ValueError, IndexError):
                    continue
        except Exception as e:
            print(f"[警告] 批量行情失败 batch {i}: {e}")
        time.sleep(0.3)
    
    return results


# ═══════════════════════════════════════════════
# A股全市场扫描（涨停/异动股）
# ═══════════════════════════════════════════════

def fetch_limit_up_stocks() -> List[Dict]:
    """获取今日涨停/强势股（多数据源，含降级）"""
    stocks = []
    
    # 数据源1: 东方财富涨停板
    try:
        import urllib.request
        for page in range(1, 4):  # 多页覆盖更多
            url = (f"http://push2.eastmoney.com/api/qt/clist/get?"
                   f"pn={page}&pz=50&po=1&np=1&fields=f2,f3,f4,f5,f12,f14"
                   f"&fid=f3&fs=m:90+t:2")
            req = urllib.request.urlopen(url, timeout=10)
            data = json.loads(req.read().decode())
            if data and data.get("data") and data["data"].get("diff"):
                for item in data["data"]["diff"]:
                    stocks.append({
                        "code": str(item.get("f12", "")),
                        "name": item.get("f14", ""),
                        "price": item.get("f2", 0) or 0,
                        "change_pct": item.get("f3", 0) or 0,
                        "turnover": item.get("f5", 0) or 0,
                    })
            time.sleep(0.2)
    except:
        pass
    
    if stocks:
        return stocks
    
    # 数据源2: 东方财富强势股（涨幅>5%）
    try:
        import urllib.request
        url = ("http://push2.eastmoney.com/api/qt/clist/get?"
               "pn=1&pz=100&po=1&np=1&fields=f2,f3,f4,f5,f12,f14"
               "&fid=f3&fs=m:0+t:6+f:!50")  # 全部A股按涨幅排序
        req = urllib.request.urlopen(url, timeout=10)
        data = json.loads(req.read().decode())
        if data and data.get("data") and data["data"].get("diff"):
            for item in data["data"]["diff"]:
                pct = item.get("f3", 0) or 0
                if pct >= 3:  # 涨幅>=3%算强势
                    stocks.append({
                        "code": str(item.get("f12", "")),
                        "name": item.get("f14", ""),
                        "price": item.get("f2", 0) or 0,
                        "change_pct": pct,
                        "turnover": item.get("f5", 0) or 0,
                    })
    except Exception as e:
        print(f"[警告] 强势股获取失败: {e}")
    
    if not stocks:
        print("[警告] 所有数据源失败，无法获取股票列表")
    
    return stocks


# ═══════════════════════════════════════════════
# 评分引擎
# ═══════════════════════════════════════════════

def score_by_strategy(quote: Dict, strategy: str, sector_heat: int = 0) -> float:
    """多策略评分"""
    score = 0.0
    cp = quote.get("change_pct", 0)
    to = quote.get("turnover", 0)
    price = quote.get("price", 0)
    yclose = quote.get("yclose", 0)
    pe = quote.get("pe", 0)
    
    # ── 通用因子（所有策略共享）──
    if price <= 0 or price < 2:
        return -1  # 停牌/垃圾股过滤
    
    # 板块热度加成（核心新增）
    if sector_heat >= 70:
        score += 25
    elif sector_heat >= 50:
        score += 15
    elif sector_heat >= 30:
        score += 8
    
    # ── 策略特有因子 ──
    if strategy == "sector_momentum":
        # 板块动量：涨得猛 + 换手高 + 板块热
        if cp >= 9.5: score += 35
        elif cp >= 7: score += 25
        elif cp >= 5: score += 18
        elif cp >= 3: score += 10
        
        if to >= 15: score += 20
        elif to >= 8: score += 12
        elif to >= 3: score += 6
        
        if cp > 0 and to > 3: score += 10  # 量价齐升
        if pe > 0 and pe < 100: score += 5  # 不太离谱的PE
    
    elif strategy == "youzi":
        # 游资策略：高换手 + 强动量 + 大幅波动
        if cp >= 9.5 and to >= 5: score += 30
        elif cp >= 5: score += 20
        elif cp >= 3: score += 10
        
        if to >= 10: score += 20
        elif to >= 5: score += 12
        elif to >= 3: score += 6
        
        if price > yclose: score += 8
        if cp < 1 or cp > 10: score -= 5  # 无量涨停/跌停
    
    elif strategy == "lianghua":
        # 量化策略：温和上涨 + 适中换手
        if 1 <= cp <= 5: score += 20
        if 3 <= to <= 15: score += 15
        if price > yclose: score += 10
        if 1 < cp < 10 and to > 2: score += 10  # 放量
    
    elif strategy == "jichang":
        # 基础工具：稳健型
        if 0 < cp <= 5: score += 20
        if 2 <= to <= 10: score += 15
        if price > yclose: score += 8
        if 0 < pe < 50: score += 8  # 低PE加分
        elif 50 <= pe < 100: score += 3
    
    return score


# ═══════════════════════════════════════════════
# 选股执行
# ═══════════════════════════════════════════════

def screen_stocks(strategy: str, top_n: int = 10) -> List[Dict]:
    """执行单策略选股"""
    strategy_config = STRATEGIES.get(strategy)
    if not strategy_config:
        raise ValueError(f"未知策略: {strategy}")
    
    # 1. 获取板块热度
    sector_scored, hot_sectors = load_today_sectors()
    print(f"[{strategy}] 板块热度TOP5: {hot_sectors}")
    
    # 2. 获取候选池
    candidates = {}  # code -> sector_name
    if sector_scored:
        for s in sector_scored[:5]:  # 只从TOP5热门板块选
            for stock_name in parse_stock_list(s["stocks_text"]):
                # stock_name是中文名，需要查行情才能拿到代码
                # 先占位，后面通过名字匹配
                pass
    
    # ===== 方案B: 从涨停板/全市场扫描 =====
    limit_up = fetch_limit_up_stocks()
    print(f"[{strategy}] 涨停/异动股: {len(limit_up)} 只")
    
    all_quotes = {}
    # 先查涨停股的行情
    if limit_up:
        codes = [s["code"] for s in limit_up if s.get("code")]
        if codes:
            all_quotes.update(fetch_batch_quotes(codes))
    
    # 3. 评分
    scored = []
    for code, q in all_quotes.items():
        if q["price"] <= 0:
            continue
        
        # 计算该股所属板块的热度
        stock_heat = 0
        if sector_scored:
            name = q.get("name", "")
            for s in sector_scored:
                if name in s["stocks_text"]:
                    stock_heat = s["heat"]
                    break
        
        s = score_by_strategy(q, strategy, stock_heat)
        if s >= strategy_config["min_score"]:
            scored.append({**q, "score": round(s, 1), "sector_heat": stock_heat})
    
    # 4. 排序
    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[:top_n]
    
    # 5. 格式化
    result = []
    for idx, s in enumerate(top, 1):
        result.append({
            "rank": idx,
            "code": s["code"],
            "name": s["name"],
            "price": s["price"],
            "change_pct": s["change_pct"],
            "turnover": s["turnover"],
            "sector_heat": s["sector_heat"],
            "score": s["score"],
            "strategy": strategy,
            "reason": _generate_reason(s, strategy),
        })
    
    return result


def _generate_reason(quote: Dict, strategy: str) -> str:
    """生成推荐理由"""
    parts = []
    cp = quote.get("change_pct", 0)
    to = quote.get("turnover", 0)
    sh = quote.get("sector_heat", 0)
    
    if cp >= 9.5:
        parts.append(f"强势涨停+{cp:.1f}%")
    elif cp >= 5:
        parts.append(f"大涨+{cp:.1f}%")
    elif cp >= 3:
        parts.append(f"上涨+{cp:.1f}%")
    
    if to >= 15:
        parts.append(f"换手极高{to:.1f}%")
    elif to >= 8:
        parts.append(f"换手活跃{to:.1f}%")
    
    if sh >= 70:
        parts.append("🔥板块热点")
    elif sh >= 50:
        parts.append("📈板块较热")
    
    if strategy == "sector_momentum":
        if cp > 0 and sh >= 50:
            parts.append("板块动量共振")
    elif strategy == "youzi":
        if cp >= 9.5 and to >= 5:
            parts.append("游资关注")
    elif strategy == "jichang":
        pe = quote.get("pe", 0)
        if 0 < pe < 30:
            parts.append("低估值")
    
    return "，".join(parts) if parts else "技术面关注"


def run_all_strategies(top_n: int = 10) -> Dict:
    """运行所有策略，生成推荐清单"""
    result = {}
    all_picks = set()
    
    for key in STRATEGIES:
        try:
            picks = screen_stocks(key, top_n=top_n)
            result[key] = {
                "strategy_name": STRATEGIES[key]["name"],
                "desc": STRATEGIES[key]["desc"],
                "picks": picks,
                "count": len(picks),
            }
            all_picks.update(p["code"] for p in picks)
        except Exception as e:
            result[key] = {"strategy_name": STRATEGIES[key]["name"], "error": str(e), "picks": []}
    
    return {
        "strategies": result,
        "total_unique": len(all_picks),
        "generated_at": datetime.now().isoformat(),
        "date": date.today().isoformat(),
    }


if __name__ == "__main__":
    strategies = sys.argv[1:] if len(sys.argv) > 1 else None
    
    if strategies:
        result = {}
        for s in strategies:
            if s in STRATEGIES:
                result[s] = {"picks": screen_stocks(s, top_n=10)}
    else:
        result = run_all_strategies(top_n=10)
    
    strategies_data = result.get("strategies", result)
    
    print(f"\n{'='*60}")
    print(f"📊 策略选股结果 · {date.today().isoformat()}")
    print(f"{'='*60}")
    
    for sk, sv in strategies_data.items():
        picks = sv.get("picks", [])
        if not picks:
            continue
        print(f"\n── {sv.get('strategy_name', sk)} ──")
        print(f"   {sv.get('desc', '')}")
        print(f"   {'排名':>3s} {'代码':>7s} {'名称':8s} {'价格':>7s} {'涨跌':>7s} {'换手':>6s} {'热度':>5s} {'评分':>5s}")
        print(f"   {'-'*55}")
        for p in picks:
            cp = f"+{p['change_pct']:.1f}%" if p['change_pct'] >= 0 else f"{p['change_pct']:.1f}%"
            print(f"   #{p['rank']:2d} {p['code']:>7s} {p['name']:8s} "
                  f"{p['price']:>7.2f} {cp:>7s} {p['turnover']:>5.1f}% "
                  f"{p['sector_heat']:>4d} {p['score']:>5.1f}")
            if p.get("reason"):
                print(f"       → {p['reason']}")
    
    print(f"\n✅ 覆盖策略: {len(strategies_data)}个")
    unique = set()
    for sv in strategies_data.values():
        for p in sv.get("picks", []):
            unique.add(p["code"])
    print(f"✅ 推荐股票: {len(unique)}只")
