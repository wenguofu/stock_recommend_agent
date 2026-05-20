"""
板块轮动趋势追踪 v1

每日盘后运行，分析板块热度变化趋势
依赖：sector_data/ 下有多天数据时自动生成趋势报告

用法: uv run python sector_trend.py
"""

import json
import os
import sys
from datetime import datetime, timedelta
from collections import defaultdict

SECTOR_DATA_DIR = os.path.join(os.path.dirname(__file__), "sector_data")


def load_all_sector_data():
    """加载所有历史板块数据"""
    files = sorted(os.listdir(SECTOR_DATA_DIR))
    json_files = [f for f in files if f.endswith(".json")]
    results = []
    for f in json_files:
        with open(os.path.join(SECTOR_DATA_DIR, f), encoding="utf-8") as fh:
            data = json.load(fh)
            results.append(data)
    return results


def compute_sector_scores(sector):
    """简化版热度评分（不依赖sector_utils）"""
    combined = sector.get("driver", "") + sector.get("insight", "") + sector.get("view", "")
    score = 10  # base
    intensity_words = ["需求爆发", "供不应求", "大涨", "飙升", "突破", "历史新高", "商业化", "景气度"]
    for w in intensity_words:
        if w in combined:
            score += 3
    total_len = len(combined)
    if total_len > 400:
        score += 5
    elif total_len > 200:
        score += 2
    return min(100, score)


def build_trend_report():
    """生成板块轮动趋势报告"""
    all_data = load_all_sector_data()
    
    if len(all_data) < 2:
        return f"已积累 {len(all_data)} 天数据，需要至少2天才能生成趋势分析。继续每天导入..."
    
    # 计算每天每个板块的热度
    daily_scores = {}  # {date: {sector_name: score}}
    all_sectors_set = set()
    
    for day_data in all_data:
        date = day_data.get("date", "?")
        scores = {}
        for i, s in enumerate(day_data.get("sectors", [])):
            heat = compute_sector_scores(s)
            # 位置加成
            heat += max(0, 10 - i)
            scores[s["name"]] = heat
            all_sectors_set.add(s["name"])
        daily_scores[date] = scores
    
    dates = sorted(daily_scores.keys())
    sorted_sectors = sorted(all_sectors_set)
    
    lines = []
    lines.append(f"# 板块轮动趋势报告")
    lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"数据覆盖: {dates[0]} ~ {dates[-1]} 共 {len(dates)} 天")
    lines.append("")
    
    # 热度矩阵
    lines.append("## 板块热度趋势矩阵")
    lines.append("")
    header = f"{'板块':12s} | " + " | ".join(d[-5:] for d in dates)
    sep = f"{':'*12}" + "|" + "|".join("-----:" for _ in dates)
    lines.append(header)
    lines.append(sep)
    
    for sn in sorted_sectors:
        row = [f"{sn:12s}"]
        for d in dates:
            s = daily_scores[d].get(sn, 0)
            # 可视化: 🔥🔥🔥🔥🔥🔥
            bars = "█" * max(1, s // 15)
            row.append(f"{bars:>5s}")
        lines.append(" | ".join(row))
    
    lines.append("")
    
    # 今日TOP5 vs 昨日TOP5
    today = dates[-1]
    yesterday = dates[-2] if len(dates) >= 2 else None
    
    today_top5 = sorted(daily_scores[today].items(), key=lambda x: -x[1])[:5]
    lines.append(f"## 📊 今日热点 TOP5 ({today})")
    for i, (name, score) in enumerate(today_top5):
        lines.append(f"  {i+1}. **{name}** ({score}分)")
    lines.append("")
    
    if yesterday:
        yesterday_top5 = sorted(daily_scores[yesterday].items(), key=lambda x: -x[1])[:5]
        today_names = {n for n, _ in today_top5}
        yesterday_names = {n for n, _ in yesterday_top5}
        
        new_entries = today_names - yesterday_names
        dropped = yesterday_names - today_names
        
        lines.append(f"## 🔄 板块轮动 (vs {yesterday})")
        if new_entries:
            lines.append(f"  🆕 **新进入TOP5**: {', '.join(new_entries)}")
        if dropped:
            lines.append(f"  ❌ **跌出TOP5**: {', '.join(dropped)}")
        if not new_entries and not dropped:
            lines.append(f"  ✅ TOP5完全一致 — 主线板块确认！")
        lines.append("")
    
    # 持续性赛道识别
    lines.append("## 🏆 持续热点发现")
    lines.append("")
    for sn in sorted_sectors:
        scores_over_time = [daily_scores[d].get(sn, 0) for d in dates]
        avg = sum(scores_over_time) / len(scores_over_time)
        trend = scores_over_time[-1] - scores_over_time[0]
        direction = "📈 升温" if trend > 10 else ("📉 降温" if trend < -10 else "➡️ 持平")
        if avg > 30:
            lines.append(f"  {direction} **{sn}** (均分{avg:.0f}, 变动{trend:+d})")
    
    return "\n".join(lines)


if __name__ == "__main__":
    report = build_trend_report()
    print(report)
    
    # Save to eval_result
    eval_dir = os.path.join(os.path.dirname(__file__), "eval_result")
    os.makedirs(eval_dir, exist_ok=True)
    report_path = os.path.join(eval_dir, f"板块轮动趋势_{datetime.now().strftime('%Y%m%d')}.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n✅ 趋势报告已保存: {report_path}")
