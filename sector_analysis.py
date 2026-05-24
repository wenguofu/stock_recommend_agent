"""
板块关联分析 → 结合当日板块热点与持仓/自选股

每日盘后运行，输出板块轮动分析报告
"""

import json
import os
import sys
from datetime import datetime

SECTOR_DATA_DIR = os.path.join(os.path.dirname(__file__), "sector_data")
from config import API_BASE


def get_latest_sector():
    """获取最新的板块数据"""
    files = sorted(os.listdir(SECTOR_DATA_DIR))
    json_files = [f for f in files if f.endswith(".json")]
    if not json_files:
        return None
    latest = json_files[-1]
    with open(os.path.join(SECTOR_DATA_DIR, latest), encoding="utf-8") as f:
        return json.load(f)


def get_holdings():
    """从API获取持仓数据"""
    import urllib.request
    try:
        req = urllib.request.Request(f"{API_BASE}/api/holdings")
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read().decode())
        return data
    except Exception as e:
        print(f"[WARN] 获取持仓失败: {e}")
        return []


def get_watchlist():
    """从API获取自选股"""
    import urllib.request
    try:
        req = urllib.request.Request(f"{API_BASE}/api/watchlist")
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read().decode())
        return data
    except Exception as e:
        print(f"[WARN] 获取自选失败: {e}")
        return []


# 股票→板块映射（手动整理，持续优化）
STOCK_SECTOR_MAP = {
    "300679": ["算力", "机器人", "光纤概念"],      # 电连技术 - 连接器
    "301696": ["机器人", "算力"],                   # 三瑞智能 - 智能控制
    "002407": ["煤炭", "算力"],                     # 多氟多 - 电解液/氟化工
    "002436": ["半导体材料", "算力"],                # 兴森科技 - PCB
    "600150": ["算力"],                             # 中国船舶 - 已清仓
    "300433": ["机器人"],                           # 蓝思科技 - 已清仓
}


def cross_reference(sector_data, holdings, watchlist):
    """板块×持仓交叉分析"""
    if not sector_data:
        return "暂无板块数据"
    
    date_str = sector_data.get("date", "")
    sectors = {s["name"]: s for s in sector_data.get("sectors", [])}
    
    lines = []
    lines.append(f"# 板块交叉分析 · {date_str}")
    lines.append("")
    
    # 分析持仓股所在的板块热度
    lines.append("## 🔍 持仓板块联动分析")
    lines.append("")
    lines.append(f"| 股票 | 关联板块 | 板块今日热度 | 板块驱动 |")
    lines.append(f"|------|---------|-------------|---------|")
    
    all_stocks = []
    if isinstance(holdings, dict) and "data" in holdings:
        all_stocks.extend(holdings["data"])
    if isinstance(watchlist, dict) and "data" in watchlist:
        all_stocks.extend(watchlist["data"])
    
    analyzed_codes = set()
    for item in all_stocks:
        code = None
        name = None
        if isinstance(item, dict):
            code = item.get("code") or item.get("symbol", "")
            name = item.get("name", code)
        else:
            continue
        
        if code in analyzed_codes or not code:
            continue
        analyzed_codes.add(code)
        
        related = STOCK_SECTOR_MAP.get(code, [])
        if not related:
            continue
        
        hot_sectors = []
        for sn in related:
            s = sectors.get(sn)
            if s:
                hot_sectors.append(f"🔥 {sn}")
            else:
                hot_sectors.append(f"⚪ {sn}")
        
        sector_drivers = "; ".join([
            sectors[sn]["driver"][:50] 
            for sn in related if sectors.get(sn)
        ]) if any(sectors.get(sn) for sn in related) else "-"
        
        codes_str = ", ".join(hot_sectors)
        lines.append(f"| {name}({code}) | {codes_str} | {sector_drivers} |")
    
    lines.append("")
    
    # 板块热度评分
    lines.append("## 🔥 板块热度评分")
    lines.append("")
    try:
        from sector_utils import score_all_sectors
        scored = score_all_sectors(sector_data)
        lines.append(f"| {'排名':>3s} | {'板块':10s} | {'评分':>4s} | {'驱动':30s} |")
        lines.append(f"|{'---:'}|{'---:'}|{'---:'}|{'---:'}|")
        for i, s in enumerate(scored[:7]):
            icon = "🔥" if s['heat_score'] >= 60 else "📈" if s['heat_score'] >= 35 else "⚪"
            lines.append(f"| {i+1:3d} | {icon} {s['name']:8s} | {s['heat_score']:4d} | {s['driver'][:28]:30s} |")
        lines.append("")
    except Exception as e:
        lines.append(f"(评分加载失败: {e})")
        lines.append("")
    
    # 当日最强板块TOP3
    lines.append("## 🏆 当日最强板块 TOP 5")
    lines.append("")
    for s in sector_data.get("sectors", [])[:5]:
        lines.append(f"### {s['name']}")
        lines.append(f"- **领涨**: {s.get('stocks', '')[:60]}")
        lines.append(f"- **驱动**: {s.get('driver', '')[:80]}")
        if s.get("view"):
            lines.append(f"- **机构**: {s['view'][:80]}")
        lines.append("")
    
    # 大盘情绪
    lines.append("## 📈 大盘情绪")
    lines.append("")
    lines.append(sector_data.get("market_summary", "")[:200])
    lines.append("")
    
    return "\n".join(lines)


def send_to_wechat(report):
    """通过API发送到微信"""
    # 保存到 eval_result
    eval_dir = os.path.join(os.path.dirname(__file__), "eval_result")
    os.makedirs(eval_dir, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    path = os.path.join(eval_dir, f"板块交叉分析_{date_str}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"✅ 分析报告已保存: {path}")
    print(report[:500])
    return path


if __name__ == "__main__":
    print("📊 板块交叉分析启动...")
    
    sector_data = get_latest_sector()
    if not sector_data:
        print("❌ 没有板块数据，请先运行 sector_import.py")
        sys.exit(1)
    
    print(f"📅 板块数据日期: {sector_data['date']}")
    print(f"📋 板块数: {len(sector_data['sectors'])}")
    
    holdings = get_holdings()
    watchlist = get_watchlist()
    
    report = cross_reference(sector_data, holdings, watchlist)
    path = send_to_wechat(report)

    # 运行主线预判引擎
    try:
        from sector_prediction import predict_sectors, format_report
        results = predict_sectors(sector_data["sectors"])
        pred_report = format_report(results, sector_data["date"])
        eval_dir = os.path.join(os.path.dirname(__file__), "eval_result")
        os.makedirs(eval_dir, exist_ok=True)
        pred_path = os.path.join(eval_dir, f"主线预判_{datetime.now().strftime('%Y%m%d')}.md")
        with open(pred_path, "w", encoding="utf-8") as f:
            f.write(pred_report)
        print(f"🔮 主线预判已保存: {pred_path}")
    except Exception as e:
        print(f"[WARN] 主线预判引擎异常: {e}")

    print(f"\n💡 使用示例:")
    print(f"   下次导入: uv run python sector_import.py 九大板块_YYYYMMDD.pdf")
    print(f"   交叉分析: uv run python sector_analysis.py")
    print(f"   主线预判: uv run python sector_prediction.py")
