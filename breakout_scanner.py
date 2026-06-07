"""
突破扫描器 v1 — 抓"长期横盘→爆量突破→缩量回踩"的票

基于新天科技(300259)的教训：5个月横盘+窒息量+天量突破+缩量洗盘=完美买点
每天扫描全市场，找出符合这种形态的股票。

用法:
    uv run python breakout_scanner.py              # 全市场扫描
    uv run python breakout_scanner.py --top 20     # 输出TOP20
    uv run python breakout_scanner.py --code 300259  # 单独分析
"""

import os, sys, json, time
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
from collections import defaultdict

# ── 配置 ──────────────────────────────────────────
API_BASE = os.environ.get("A_STOCK_API", "http://127.0.0.1:35000")
EVAL_DIR = os.path.join(os.path.dirname(__file__), "eval_result")

# 扫描参数
MIN_CONSOLIDATION_DAYS = 40     # 至少横盘40个交易日（约2个月）
MAX_CONSOLIDATION_RANGE = 0.25  # 横盘区间振幅<25%
MIN_VOLUME_EXPANSION = 2.5      # 突破日量能是横盘均量的2.5倍+
MIN_BREAKOUT_PCT = 8.0          # 突破日涨幅>8%（涨停或准涨停）
PULLBACK_RANGE = (0.35, 0.70)   # 回踩到突破涨幅的35-70%（健康回踩）

# ── 数据获取 ──────────────────────────────────────
def api_get(path, timeout=15):
    try:
        req = Request(f"{API_BASE}{path}", headers={'User-Agent': 'scanner/1.0'})
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except:
        return None

def get_daily_kline(code, days=180):
    """获取日K线"""
    data = api_get(f"/api/kline/{code}?days={days}")
    if not data or not data.get("success"):
        return None
    return data.get("data", [])

# ── 形态识别 ──────────────────────────────────────
def detect_consolidation(kline_data):
    """
    识别长期窄幅横盘。
    返回 (横盘起始索引, 横盘结束索引, 最高价, 最低价, 均量) 或 None
    """
    if not kline_data or len(kline_data) < MIN_CONSOLIDATION_DAYS + 10:
        return None

    closes = [d["close"] for d in kline_data]
    highs = [d["high"] for d in kline_data]
    lows = [d["low"] for d in kline_data]
    volumes = [d["volume"] for d in kline_data]

    # 从后往前找：找最近一段横盘（在突破之前）
    # 先找突破点：收盘价明显高于前20日均价的位置
    n = len(kline_data)
    breakout_idx = None

    for i in range(n-5, MIN_CONSOLIDATION_DAYS, -1):
        if i < 60:
            break
        ma20 = sum(closes[i-20:i]) / 20
        if closes[i] > ma20 * 1.15:  # 突破15%+
            high_before = max(highs[i-60:i])
            if closes[i] > high_before * 1.05:  # 突破60日前高
                breakout_idx = i
                break

    if breakout_idx is None:
        return None

    # 从突破点往前找横盘区间
    cons_end = breakout_idx - 1
    # 往前找60天内的高低价范围
    lookback = min(60, cons_end)
    cons_start = cons_end - lookback + 1

    cons_high = max(highs[cons_start:cons_end+1])
    cons_low = min(lows[cons_start:cons_end+1])
    cons_range = (cons_high - cons_low) / cons_low

    if cons_range > MAX_CONSOLIDATION_RANGE:
        # 振幅太大，不是横盘
        return None

    cons_avg_vol = sum(volumes[cons_start:cons_end+1]) / (cons_end - cons_start + 1)

    return (cons_start, cons_end, cons_high, cons_low, cons_avg_vol, breakout_idx)


def detect_pullback(kline_data, breakout_idx, breakout_pct):
    """
    检测突破后的缩量回踩。
    返回 (回踩日索引, 回踩价格, 回踩幅度%) 或 None
    """
    if breakout_idx >= len(kline_data) - 3:
        return None  # 突破后数据不够

    closes = [d["close"] for d in kline_data]
    volumes = [d["volume"] for d in kline_data]
    breakout_price = closes[breakout_idx]
    breakout_vol = volumes[breakout_idx]

    # 找突破后回踩日（最近几天）
    for i in range(breakout_idx + 1, min(breakout_idx + 8, len(kline_data))):
        pullback_pct = (closes[i] - breakout_price) / breakout_price * 100
        vol_ratio = volumes[i] / breakout_vol if breakout_vol > 0 else 1

        # 回踩：价格回调到突破涨幅的35-70%
        if PULLBACK_RANGE[0] * breakout_pct / 100 <= abs(pullback_pct) / (breakout_pct/100) <= PULLBACK_RANGE[1] * breakout_pct / 100:
            if vol_ratio < 0.7:  # 缩量（量<突破日的70%）
                return (i, closes[i], pullback_pct)

    return None


# ── Stock list ──────────────────────────────────────
def get_stock_list():
    """Get candidate stocks from multiple sources"""
    codes = set()

    # 1. Watchlist
    wl = api_get("/api/watchlist")
    if wl and wl.get("success"):
        for s in wl.get("data", []):
            codes.add(s["code"])

    # 2. Sector leaders
    sector_data_dir = os.path.join(os.path.dirname(__file__), "sector_data")
    json_files = sorted([f for f in os.listdir(sector_data_dir) if f.endswith(".json")], reverse=True)
    if json_files:
        with open(os.path.join(sector_data_dir, json_files[0])) as f:
            sd = json.load(f)
        for sec in sd.get("sectors", []):
            for stock_name in sec.get("stocks", "").split("、"):
                pass  # names only, no codes

    # 3. Key sector stocks from sector_prediction mapping
    from sector_prediction import SECTOR_STOCK_MAP
    for codes_list in SECTOR_STOCK_MAP.values():
        codes.update(codes_list)

    # Fallback: scan some representative codes
    if len(codes) < 20:
        # Add some major sector representatives
        extra = ["000001", "600519", "601318", "000858", "002594",
                 "300750", "688981", "603986", "300433", "300679",
                 "300259", "002049", "300136", "600150", "002407"]
        codes.update(extra)

    return sorted(codes)[:200]  # limit to 200 to avoid overwhelming


# ── Report ──────────────────────────────────────────
def scan_all():
    codes = get_stock_list()
    print(f"🔍 扫描 {len(codes)} 只股票...")

    results = []
    for i, code in enumerate(codes):
        if i % 20 == 0:
            print(f"  进度: {i}/{len(codes)}")

        kline = get_daily_kline(code, 180)
        if not kline:
            continue

        # Get stock name
        info = api_get(f"/api/sina/realtime/{code}")
        name = info.get("name", code) if info else code

        cons = detect_consolidation(kline)
        if cons is None:
            continue

        cons_start, cons_end, cons_high, cons_low, cons_avg_vol, breakout_idx = cons
        closes = [d["close"] for d in kline]
        volumes = [d["volume"] for d in kline]

        breakout_price = closes[breakout_idx]
        breakout_vol = volumes[breakout_idx]
        breakout_pct = (breakout_price - cons_high) / cons_high * 100

        # Check volume expansion
        vol_expansion = breakout_vol / cons_avg_vol if cons_avg_vol > 0 else 0
        if vol_expansion < MIN_VOLUME_EXPANSION:
            continue

        # Check breakout strength
        if breakout_pct < MIN_BREAKOUT_PCT:
            continue

        # Check for pullback
        pb = detect_pullback(kline, breakout_idx, breakout_pct)
        latest_close = closes[-1]
        latest_vol = volumes[-1]

        # Score the setup
        score = 0
        cons_days = cons_end - cons_start + 1
        score += min(30, cons_days / 2)          # Longer base = better
        score += min(20, vol_expansion * 4)       # More volume = better
        score += min(15, breakout_pct)            # Stronger breakout = better
        score += min(15, 15 - abs((latest_close - breakout_price) / breakout_price * 100))  # Close to breakout = better

        # Deduction if already too far extended
        ext_pct = (latest_close - cons_low) / cons_low * 100
        if ext_pct > 80:
            score -= 20

        signal_type = "无回踩" if pb is None else "✅ 有回踩"
        pullback_price = pb[1] if pb else None

        results.append({
            "code": code,
            "name": name,
            "score": round(score, 1),
            "cons_days": cons_days,
            "cons_range": round((cons_high - cons_low) / cons_low * 100, 1),
            "breakout_date": kline[breakout_idx].get("date", "?"),
            "breakout_price": breakout_price,
            "breakout_pct": round(breakout_pct, 1),
            "vol_expansion": round(vol_expansion, 1),
            "latest": latest_close,
            "ext_pct": round(ext_pct, 1),
            "pullback": signal_type,
            "pullback_price": pullback_price,
        })

        time.sleep(0.3)  # Rate limit

    results.sort(key=lambda x: -x["score"])
    return results


def format_report(results, top_n=20):
    lines = [
        "# 🔍 底部突破扫描报告",
        f"扫描时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"模式: 长期横盘 → 爆量突破 → 缩量回踩",
        f"扫描范围: {len(results)} 只候选（≥{MIN_CONSOLIDATION_DAYS}天横盘 + {MIN_VOLUME_EXPANSION}x量 + {MIN_BREAKOUT_PCT}%涨幅）",
        "",
        "## 📊 扫描结果 TOP{top_n}",
        "",
        "| 排名 | 代码 | 名称 | 评分 | 横盘天数 | 振幅% | 突破日 | 突破涨幅% | 量比 | 延伸% | 回踩 |",
        "|:---:|------|------|:---:|:---:|:---:|------|:---:|:---:|:---:|------|",
    ]

    for i, r in enumerate(results[:top_n]):
        pb_str = r["pullback"]
        if r["pullback_price"]:
            pb_str += f" @{r['pullback_price']:.2f}"

        lines.append(
            f"| {i+1} | {r['code']} | {r['name']} | "
            f"{r['score']:.0f} | {r['cons_days']} | {r['cons_range']} | "
            f"{r['breakout_date']} | {r['breakout_pct']} | {r['vol_expansion']}x | "
            f"{r['ext_pct']} | {pb_str} |"
        )

    lines.append("")
    lines.append("## 🏆 重点关注（有回踩信号的票）")
    lines.append("")

    pullback_results = [r for r in results if "有回踩" in r.get("pullback", "")]
    if pullback_results:
        for r in pullback_results[:10]:
            lines.append(f"### {r['name']}({r['code']}) — 评分 {r['score']:.0f}")
            lines.append(f"- 横盘 {r['cons_days']}天，振幅 {r['cons_range']}%")
            lines.append(f"- 突破日 {r['breakout_date']}，涨幅 {r['breakout_pct']}%，量比 {r['vol_expansion']}x")
            lines.append(f"- 回踩价 ¥{r['pullback_price']:.2f}，当前 ¥{r['latest']:.2f}（延伸 {r['ext_pct']}%）")
            lines.append("")
    else:
        lines.append("无符合条件的回踩信号。继续等待。")

    lines.append("---")
    lines.append(f"*扫描器 v1 · {datetime.now().strftime('%Y-%m-%d')}*")
    return "\n".join(lines)


def main():
    """修复 BUG-11: 返回 dict 而非 print/exit, 供模块化调用"""
    os.makedirs(EVAL_DIR, exist_ok=True)
    args = sys.argv[1:]

    top_n = 20
    target_code = None
    for i, arg in enumerate(args):
        if arg == "--top" and i + 1 < len(args):
            top_n = int(args[i+1])
        elif arg == "--code" and i + 1 < len(args):
            target_code = args[i+1]

    if target_code:
        kline = get_daily_kline(target_code, 180)
        if not kline:
            return {"success": False, "error": f"无法获取 {target_code} 的K线数据"}
        info = api_get(f"/api/sina/realtime/{target_code}")
        name = info.get("name", target_code) if info else target_code
        cons = detect_consolidation(kline)
        return {
            "success": True,
            "code": target_code,
            "name": name,
            "breakout_detected": bool(cons),
            "details": cons or {},
        }

    results = scan_all()
    report = format_report(results, top_n)

    path = os.path.join(EVAL_DIR, f"突破扫描_{datetime.now().strftime('%Y%m%d')}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)
    return {
        "success": True,
        "report": report,
        "report_path": path,
        "results": results,
        "top_n": top_n,
    }


if __name__ == "__main__":
    main()
