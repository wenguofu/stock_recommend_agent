"""
策略验证系统 v1

记录每次选股结果 → 跟踪后续表现 → 计算策略胜率

数据：strategy_picks/*.json (每日历史)
报告：桌面 策略验证报告_YYYYMMDD.md

用法:
  uv run python strategy_validator.py          # 查看最新验证
  uv run python strategy_validator.py --report  # 生成完整报告
"""

import json
import os
import sys
import time
from datetime import datetime, date, timedelta
from collections import defaultdict

PROJECT_DIR = os.path.dirname(__file__)
PICKS_DIR = os.path.join(PROJECT_DIR, "strategy_picks")
REPORT_DIR = os.path.join(os.path.dirname(__file__), "eval_result")


# ═══════════════════════════════════════════════
# 记录选股结果
# ═══════════════════════════════════════════════

def save_picks(strategy_results: dict):
    """将选股结果存入历史"""
    os.makedirs(PICKS_DIR, exist_ok=True)
    
    today = date.today().isoformat()
    
    # 已有记录
    record_path = os.path.join(PICKS_DIR, f"{today}.json")
    if os.path.exists(record_path):
        with open(record_path, encoding="utf-8") as f:
            existing = json.load(f)
    else:
        existing = {"date": today, "picks": []}
    
    strategies_data = strategy_results.get("strategies", strategy_results)
    for sk, sv in strategies_data.items():
        for p in sv.get("picks", []):
            pick_record = {
                "code": p["code"],
                "name": p["name"],
                "price": p["price"],
                "change_pct": p["change_pct"],
                "turnover": p["turnover"],
                "score": p["score"],
                "strategy": sk,
                "strategy_name": sv.get("strategy_name", sk),
                "reason": p.get("reason", ""),
                "recorded_at": datetime.now().isoformat(),
                "validated": False,
                "exit_price": None,
                "exit_change_pct": None,
            }
            # 去重：同一天同一策略同一股不重复记录
            dup = False
            for ep in existing["picks"]:
                if (ep["code"] == pick_record["code"] 
                    and ep["strategy"] == pick_record["strategy"]):
                    dup = True
                    break
            if not dup:
                existing["picks"].append(pick_record)
    
    with open(record_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    
    total = len(existing["picks"])
    print(f"✅ 选股记录已保存 ({today})，累计 {total} 条")


# ═══════════════════════════════════════════════
# 验证历史选股
# ═══════════════════════════════════════════════

def validate_pick(code: str, record_price: float) -> dict:
    """验证一支历史选股的当前表现（对比记录价）"""
    try:
        suffix = f"sh{code}" if code.startswith(("5", "6", "9")) else f"sz{code}"
        import urllib.request
        url = f"http://qt.gtimg.cn/q={suffix}"
        req = urllib.request.urlopen(url, timeout=5)
        raw = req.read().decode("gbk")
        parts = raw.split("~")
        if len(parts) < 40:
            return {"error": "数据不足"}
        
        current_price = float(parts[3])
        change_pct = round((current_price - record_price) / record_price * 100, 2)
        
        return {
            "current_price": current_price,
            "change_pct": change_pct,
            "high": float(parts[33]) if parts[33] else 0,
            "low": float(parts[34]) if parts[34] else 0,
            "volume": int(parts[6]) if parts[6] else 0,
            "success": change_pct > 0,
        }
    except Exception as e:
        return {"error": str(e)}


def validate_all_strategy_picks():
    """验证所有未验证的历史选股"""
    files = sorted(os.listdir(PICKS_DIR))
    json_files = [f for f in files if f.endswith(".json")]
    
    results = {
        "validated_count": 0,
        "success_count": 0,
        "fail_count": 0,
        "total_return": 0.0,
        "by_strategy": defaultdict(lambda: {
            "total": 0, "success": 0, "fail": 0, "return_sum": 0.0
        }),
    }
    
    for fname in json_files:
        path = os.path.join(PICKS_DIR, fname)
        with open(path, encoding="utf-8") as f:
            day_data = json.load(f)
        
        changed = False
        for pick in day_data.get("picks", []):
            if pick.get("validated"):
                continue  # 已验证的跳过
            
            # 只验证超过1天的选股
            record_date = day_data.get("date", "")
            try:
                d1 = datetime.strptime(record_date, "%Y-%m-%d")
                d2 = datetime.now()
                days_diff = (d2 - d1).days
                if days_diff < 1:
                    continue  # 今天选的，明天再验证
            except:
                continue
            
            result = validate_pick(pick["code"], pick["price"])
            if "error" in result:
                continue
            
            pick["validated"] = True
            pick["exit_price"] = result["current_price"]
            pick["exit_change_pct"] = result["change_pct"]
            pick["validated_at"] = datetime.now().isoformat()
            changed = True
            
            results["validated_count"] += 1
            strat = pick.get("strategy", "unknown")
            results["by_strategy"][strat]["total"] += 1
            results["by_strategy"][strat]["return_sum"] += result["change_pct"]
            
            if result["success"]:
                results["success_count"] += 1
                results["by_strategy"][strat]["success"] += 1
            else:
                results["fail_count"] += 1
                results["by_strategy"][strat]["fail"] += 1
            
            results["total_return"] += result["change_pct"]
        
        if changed:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(day_data, f, ensure_ascii=False, indent=2)
    
    return results


# ═══════════════════════════════════════════════
# 策略评分报告
# ═══════════════════════════════════════════════

def generate_scoring_report(validation_results: dict) -> str:
    """生成策略评分报告"""
    by_strat = validation_results.get("by_strategy", {})
    
    lines = []
    lines.append(f"# 策略评分报告")
    lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    
    total = validation_results.get("validated_count", 0)
    success = validation_results.get("success_count", 0)
    fail = validation_results.get("fail_count", 0)
    total_return = validation_results.get("total_return", 0)
    
    lines.append("## 📊 整体表现")
    lines.append(f"| 指标 | 数值 |")
    lines.append(f"|------|------|")
    lines.append(f"| 已验证次数 | {total} |")
    lines.append(f"| 成功（上涨） | {success} |")
    lines.append(f"| 失败（下跌） | {fail} |")
    win_rate = round(success / total * 100, 1) if total > 0 else 0
    lines.append(f"| **胜率** | **{win_rate}%** |")
    avg_return = round(total_return / total, 2) if total > 0 else 0
    lines.append(f"| **平均收益率** | **{avg_return}%** |")
    lines.append("")
    
    # 各策略对比
    lines.append("## 🏆 策略排行")
    lines.append("")
    lines.append(f"| {'排名':>3s} | {'策略':12s} | {'次数':>5s} | {'胜':>4s} | {'负':>4s} | {'胜率':>7s} | {'平均收益':>10s} |")
    lines.append(f"|{'---:'}|{'---:'}|{'---:'}|{'---:'}|{'---:'}|{'---:'}|{'---:'}|")
    
    # 按胜率排序
    sorted_strats = sorted(
        by_strat.items(),
        key=lambda x: x[1]["success"] / max(x[1]["total"], 1),
        reverse=True,
    )
    
    for rank, (sk, sv) in enumerate(sorted_strats, 1):
        sr = round(sv["success"] / max(sv["total"], 1) * 100, 1)
        ar = round(sv["return_sum"] / max(sv["total"], 1), 2)
        lines.append(f"| {rank:3d} | {sk:12s} | {sv['total']:5d} | {sv['success']:4d} | "
                     f"{sv['fail']:4d} | {sr:>6.1f}% | {ar:>+9.2f}% |")
    
    lines.append("")
    
    # 最新推荐 vs 验证结果
    lines.append("## 💡 使用建议")
    lines.append("")
    if total < 5:
        lines.append("⚠️ 数据量不足（<5次验证），暂时无法给出可靠策略排名。")
        lines.append("继续每日运行选股+验证，积累数据后自动出评分。")
    else:
        top_strat = sorted_strats[0][0] if sorted_strats else ""
        lines.append(f"当前最佳策略: **{top_strat}** (胜率{sr}%)")
        lines.append(f"整体平均收益: **{avg_return}%**")
        if win_rate > 50:
            lines.append("✅ 系统有效，建议持续使用")
        else:
            lines.append("⚠️ 策略需要优化，建议结合板块热度调参")
    
    return "\n".join(lines)


def get_all_picks_history() -> list:
    """获取所有历史选股记录"""
    files = sorted(os.listdir(PICKS_DIR))
    all_picks = []
    for fname in files:
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(PICKS_DIR, fname), encoding="utf-8") as f:
            data = json.load(f)
        for p in data.get("picks", []):
            p["pick_date"] = data["date"]
            all_picks.append(p)
    return all_picks


def get_strategy_rankings() -> list:
    """获取策略排名（供API调用）"""
    all_picks = get_all_picks_history()
    
    strat_stats = defaultdict(lambda: {"total": 0, "wins": 0, "return_sum": 0.0})
    for p in all_picks:
        if not p.get("validated"):
            continue
        sk = p.get("strategy", "unknown")
        strat_stats[sk]["total"] += 1
        strat_stats[sk]["return_sum"] += p.get("exit_change_pct", 0)
        if p.get("exit_change_pct", 0) > 0:
            strat_stats[sk]["wins"] += 1
    
    rankings = []
    for sk, sv in strat_stats.items():
        rankings.append({
            "strategy": sk,
            "total": sv["total"],
            "wins": sv["wins"],
            "win_rate": round(sv["wins"] / max(sv["total"], 1) * 100, 1),
            "avg_return": round(sv["return_sum"] / max(sv["total"], 1), 2),
        })
    
    rankings.sort(key=lambda x: x["win_rate"], reverse=True)
    return rankings


if __name__ == "__main__":
    if "--report" in sys.argv:
        # 验证 + 报告
        results = validate_all_strategy_picks()
        report = generate_scoring_report(results)
        report_path = os.path.join(REPORT_DIR, f"策略评分报告_{datetime.now().strftime('%Y%m%d')}.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(report)
        print(f"\n✅ 报告已保存: {report_path}")
    else:
        # 仅验证
        results = validate_all_strategy_picks()
        vc = results["validated_count"]
        sc = results["success_count"]
        fc = results["fail_count"]
        print(f"\n📊 策略验证结果")
        print(f"   新验证: {vc} 次")
        print(f"   成功: {sc} | 失败: {fc}")
        if vc > 0:
            print(f"   胜率: {round(sc/vc*100, 1)}%")
