"""
板块数据工具集 v1

功能：
1. 板块热度评分（多维度量化）
2. 辩论Agent prompt格式化
3. 历史趋势聚合
"""

import json
import os
import re
from datetime import datetime, timedelta

from config import API_BASE

SECTOR_DATA_DIR = os.path.join(os.path.dirname(__file__), "sector_data")


# ── 1. 板块热度评分 ──

# 强度关键词（出现在driver/insight中 → 加分）
INTENSITY_KEYWORDS = {
    # 强烈信号 (+3)
    "需求爆发": 3, "供不应求": 3, "大涨": 3, "飙升": 3,
    "突破": 3, "重大": 3, "历史新高": 3, "全面超预期": 3,
    "商业化": 3, "资本支出": 3, "大幅上调": 3,
    # 中度信号 (+2)
    "景气度": 2, "上行通道": 2, "持续释放": 2, "加速": 2,
    "国产替代": 2, "政策": 2, "战略": 2, "全球": 2,
    "看好": 2, "高景气": 2, "万亿": 2,
    # 弱信号 (+1)
    "估值修复": 1, "关注": 1, "增长": 1, "需求": 1,
    "投资": 1, "空间": 1, "预期": 1,
}

# 机构背书加分
BROKERAGE_BONUS = {
    "华泰证券": 2, "中信建投": 2, "东吴证券": 2,
    "西部证券": 2, "华创证券": 2, "国投证券": 2,
    "东海证券": 2, "山西证券": 2, "财信证券": 2,
    "长城证券": 2,
}


def score_sector(sector):
    """板块热度综合评分（0-100）"""
    score = 0
    
    # 1. 位置评分（由外部传入，默认中间分）
    # 在调用时根据排名加权
    
    # 2. 驱动因素强度
    driver = sector.get("driver", "")
    insight = sector.get("insight", "")
    view = sector.get("view", "")
    combined = driver + insight + view
    
    for kw, pts in INTENSITY_KEYWORDS.items():
        count = combined.count(kw)
        score += count * pts
    
    # 3. 机构背书
    for bk, pts in BROKERAGE_BONUS.items():
        if bk in view:
            score += pts
    
    # 4. 内容长度因子（信息量）
    total_len = len(driver) + len(insight) + len(view)
    if total_len > 400:
        score += 10  # 信息丰富的板块
    elif total_len > 250:
        score += 5
    
    # 5. 领涨个股数量因子（板块宽度）
    stocks = sector.get("stocks", "")
    stock_count = len([s for s in stocks.replace("、", ",").split(",") if s.strip()])
    if stock_count >= 8:
        score += 8
    elif stock_count >= 5:
        score += 4
    
    # 6. 负面信号扣分
    negative_signals = ["回调", "压力", "有限", "分化", "风险", "不低估"]
    for ns in negative_signals:
        if ns in combined:
            score -= 2
    
    return max(0, min(100, score))


def score_all_sectors(sectors_data):
    """给所有板块打分并排序"""
    sectors = sectors_data.get("sectors", [])
    results = []
    for i, s in enumerate(sectors):
        heat = score_sector(s)
        # 位置加权：越靠前排名越高（1st=+10, 9th=-10）
        pos_bonus = max(-10, 10 - i * 2.5)
        final_score = heat + pos_bonus
        results.append({
            "name": s["name"],
            "stocks": s.get("stocks", ""),
            "heat_score": round(final_score),
            "raw_score": heat,
            "position_bonus": round(pos_bonus),
            "driver": s.get("driver", "")[:60],
        })
    results.sort(key=lambda x: x["heat_score"], reverse=True)
    return results


# ── 2. 辩论Agent上下文格式化 ──

def format_for_debate(sectors_data, holdings_context=""):
    """格式化为Agent可见的板块上下文"""
    scored = score_all_sectors(sectors_data)
    date_str = sectors_data.get("date", "unknown")
    market = sectors_data.get("market_summary", "")[:150]
    
    lines = [
        f"【市场背景 · {date_str}】",
        f"大盘：{market}",
        "",
        "【板块热度排行】",
    ]
    
    for i, s in enumerate(scored):
        icon = "🔥" if s["heat_score"] >= 60 else "📈" if s["heat_score"] >= 35 else "⚪"
        lines.append(f"  {i+1}. {icon} {s['name']:10s} 评分{s['heat_score']:3d} | {s['driver']}")
    
    if holdings_context:
        lines.append("")
        lines.append(holdings_context)
    
    return "\n".join(lines)


def get_holdings_sector_context():
    """从API获取持仓并关联板块"""
    # 股票→板块映射（与sector_analysis.py保持一致）
    STOCK_SECTOR_MAP = {
        "300679": ["算力", "机器人", "光纤概念"],
        "301696": ["机器人", "算力"],
        "002407": ["煤炭", "算力"],
        "002436": ["半导体材料", "算力"],
    }
    
    import urllib.request
    try:
        req = urllib.request.Request(f"{API_BASE}/api/holdings")
        resp = urllib.request.urlopen(req, timeout=3)
        data = json.loads(resp.read().decode())
        holdings = data.get("data", [])
    except:
        holdings = []
    
    lines = ["【你的持仓板块关联】"]
    for h in holdings:
        code = h.get("code", "")
        name = h.get("name", code)
        sectors = STOCK_SECTOR_MAP.get(code, [])
        if sectors:
            lines.append(f"  {name}({code}) → {', '.join(sectors)}")
    
    if len(lines) == 1:
        return ""
    return "\n".join(lines)


# ── 3. 历史趋势 ──

def get_latest_sector(n=1):
    """获取最近N天的板块数据"""
    files = sorted(os.listdir(SECTOR_DATA_DIR))
    json_files = sorted([f for f in files if f.endswith(".json")])
    results = []
    for f in json_files[-n:]:
        with open(os.path.join(SECTOR_DATA_DIR, f), encoding="utf-8") as fh:
            results.append(json.load(fh))
    return results[-1] if n == 1 else results


def get_trend_report(days=5):
    """生成板块轮动趋势报告（需要多天数据）"""
    data_list = get_latest_sector(days)
    if len(data_list) < 2:
        return "趋势分析需要至少2天数据，继续积累中..."
    
    lines = [f"# 板块轮动趋势 · {data_list[0]['date']} ~ {data_list[-1]['date']}", ""]
    
    # TODO: 积累更多数据后实现趋势分析
    lines.append(f"已积累 {len(data_list)} 天数据，继续收集后将自动生成：")
    lines.append("1. 板块持续性评分（连续X天在TOP3 → 主线确认）")
    lines.append("2. 轮动方向识别（资金从A板块切换到B板块）")
    lines.append("3. 持仓风险预警（持仓板块集体降温 → 建议减仓）")
    
    return "\n".join(lines)


# ── 4. 辩论结论复盘 ──

def compare_debate_with_sector(debate_conclusion, sector_data):
    """对比辩论结论与板块背景，评估一致性"""
    # 这个需要存辩论结论到数据库，等有积累后实现
    pass
