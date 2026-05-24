#!/usr/bin/env python3
"""
DB全量突破扫描器 v1 — 直接读 backtest_data，扫全市场4804只股票

比API版快100倍：一次SQL查询拿所有股票180天数据，批量处理。
寻找：长期横盘→爆量突破→缩量回踩 形态

用法:
    uv run python db_scanner.py                # 全量扫描
    uv run python db_scanner.py --top 30       # 只输出TOP30
    uv run python db_scanner.py --min-days 60  # 最小横盘60天
"""

import sqlite3
import os
import sys
from datetime import datetime

# ── 配置 ──────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")
EVAL_DIR = os.path.join(os.path.dirname(__file__), "eval_result")

MIN_CONSOLIDATION_DAYS = 40     # 最少横盘40天
MAX_CONSOLIDATION_RANGE = 0.25  # 横盘振幅<25%
MIN_VOLUME_EXPANSION = 2.0      # 突破量比>2x
MIN_BREAKOUT_PCT = 5.0          # 突破日涨幅>5%
LOOKBACK_DAYS = 180             # 取180天数据
SCORE_TOP_N = 30                # 最终输出前N只
MAX_BREAKOUT_AGE = 30           # 突破必须在最近30天内
MIN_EXT_PCT = -5                # 当前价不能低于横盘底部5%以上（过滤失败突破）


def get_all_stocks_kline(db_path, min_records=60):
    """一次性从DB拉所有股票的K线数据"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 先找数据量足够（≥min_records天）的股票
    cur.execute("""
        SELECT code, COUNT(*) as cnt
        FROM backtest_data
        GROUP BY code
        HAVING cnt >= ?
        ORDER BY cnt DESC
    """, (min_records,))

    codes = [r[0] for r in cur.fetchall()]
    print(f"📊 {len(codes)} 只股票有≥{min_records}天数据，开始拉K线...")

    # 批量拉取所有股票最近LOOKBACK_DAYS的K线
    stock_data = {}
    for i, code in enumerate(codes):
        cur.execute("""
            SELECT date, open, high, low, close, volume
            FROM backtest_data
            WHERE code = ?
            ORDER BY date DESC
            LIMIT ?
        """, (code, LOOKBACK_DAYS))
        rows = cur.fetchall()
        if len(rows) >= min_records:
            # 转换成按日期升序排列的字典列表
            data = []
            for row in reversed(rows):
                data.append({
                    "date": row[0],
                    "open": row[1], "high": row[2],
                    "low": row[3], "close": row[4],
                    "volume": row[5],
                })
            stock_data[code] = data

        if (i + 1) % 500 == 0:
            print(f"  已加载 {i+1}/{len(codes)}...")

    conn.close()
    print(f"✅ 完成：{len(stock_data)} 只股票可用")
    return stock_data


def detect_breakout(kline_data):
    """
    检测"长期横盘→爆量突破→缩量回踩"形态。
    返回字典或None。
    """
    n = len(kline_data)
    if n < MIN_CONSOLIDATION_DAYS + 10:
        return None

    closes = [d["close"] for d in kline_data]
    highs = [d["high"] for d in kline_data]
    lows = [d["low"] for d in kline_data]
    volumes = [d["volume"] for d in kline_data]
    dates = [d["date"] for d in kline_data]

    # ── Step 1: 找到最近的突破点 ──
    breakout_idx = None
    breakout_pct = 0

    for i in range(n - 3, max(MIN_CONSOLIDATION_DAYS, 60), -1):
        # 成交量放大
        avg_vol_20 = sum(volumes[max(0, i-20):i]) / min(20, i)
        if avg_vol_20 <= 0:
            continue

        vol_ratio = volumes[i] / avg_vol_20
        if vol_ratio < MIN_VOLUME_EXPANSION:
            continue

        # 价格突破前期震荡区间高点
        # 找60天前的高点
        lookback_high = max(highs[max(0, i-60):i])
        if closes[i] <= lookback_high * 0.95:  # 允许5%容差
            continue

        # 当日涨幅
        day_pct = (closes[i] - closes[i-1]) / closes[i-1] * 100 if closes[i-1] > 0 else 0
        if day_pct < MIN_BREAKOUT_PCT:
            continue

        breakout_idx = i
        breakout_pct = day_pct
        break

    if breakout_idx is None:
        return None

    # ── Step 2: 检测突破前的横盘区间 ──
    cons_end = breakout_idx - 1
    cons_start = max(0, cons_end - 80)  # 往前看80天

    cons_high = max(highs[cons_start:cons_end+1])
    cons_low = min(lows[cons_start:cons_end+1])
    cons_range = (cons_high - cons_low) / cons_low if cons_low > 0 else 999

    if cons_range > MAX_CONSOLIDATION_RANGE:
        return None

    # 横盘持续天数
    cons_days = cons_end - cons_start + 1
    if cons_days < MIN_CONSOLIDATION_DAYS:
        return None

    # 横盘均量
    cons_volumes = volumes[cons_start:cons_end+1]
    cons_avg_vol = sum(cons_volumes) / len(cons_volumes) if cons_volumes else 0
    if cons_avg_vol <= 0:
        return None

    # ── Step 3: 突破量比 ──
    vol_expansion = volumes[breakout_idx] / cons_avg_vol
    if vol_expansion < MIN_VOLUME_EXPANSION:
        return None

    # ── Step 4: 检测回踩 ──
    pullback_info = None
    breakout_price = closes[breakout_idx]
    breakout_vol = volumes[breakout_idx]

    for i in range(breakout_idx + 1, min(breakout_idx + 10, n)):
        pb_pct = (closes[i] - breakout_price) / breakout_price * 100 if breakout_price > 0 else 0
        vol_ratio = volumes[i] / breakout_vol if breakout_vol > 0 else 1

        # 缩量回踩到突破位附近（-15% ~ +5%区间）
        if -15 <= pb_pct <= 5 and vol_ratio < 0.7:
            pullback_info = {
                "idx": i,
                "date": dates[i],
                "price": round(closes[i], 2),
                "pct": round(pb_pct, 1),
                "vol_ratio": round(vol_ratio, 2),
            }
            break

    # ── Step 5: 时效性和延伸过滤 ──
    latest = closes[-1]
    latest_date = dates[-1]

    # 过滤：突破必须在最近MAX_BREAKOUT_AGE天内
    # 简单判断：用数据索引距离
    data_age = n - breakout_idx  # 突破距今多少根K线
    if data_age > MAX_BREAKOUT_AGE * 1.5:  # 给1.5x宽容因为周末
        return None

    # 过滤：当前价不能严重跌破横盘底部（过滤失败突破）
    ext_pct = (latest - cons_low) / cons_low * 100 if cons_low > 0 else 0
    if ext_pct < MIN_EXT_PCT:
        return None

    # ── Step 6: 评分 ──
    score = 0
    score += min(30, cons_days / 2)              # 横盘天数
    score += min(25, vol_expansion * 5)           # 量比
    score += min(15, breakout_pct)               # 突破涨幅
    score += min(15, 15 - abs(cons_range * 100)) # 横盘越窄越好
    score += 15 if pullback_info else 0           # 有回踩加分

    # 如果从底部涨太多，扣分
    ext_pct = (closes[-1] - cons_low) / cons_low * 100 if cons_low > 0 else 0
    if ext_pct > 100:
        score -= 20
    elif ext_pct > 60:
        score -= 10

    return {
        "cons_days": cons_days,
        "cons_range": round(cons_range * 100, 1),
        "cons_high": round(cons_high, 2),
        "cons_low": round(cons_low, 2),
        "breakout_date": dates[breakout_idx],
        "breakout_price": round(breakout_price, 2),
        "breakout_pct": round(breakout_pct, 1),
        "vol_expansion": round(vol_expansion, 1),
        "pullback": pullback_info,
        "latest": round(latest, 2),
        "ext_pct": round(ext_pct, 1),
        "score": round(score, 1),
    }


def scan_all(stock_data):
    """扫描所有股票"""
    results = []
    total = len(stock_data)
    for i, (code, kline) in enumerate(stock_data.items()):
        if (i + 1) % 500 == 0:
            print(f"  扫描进度: {i+1}/{total}, 已发现 {len(results)} 个形态")

        info = detect_breakout(kline)
        if info:
            info["code"] = code
            results.append(info)

    results.sort(key=lambda x: -x["score"])
    return results


def format_report(results, top_n):
    """生成Markdown报告"""
    lines = [
        f"# 📊 全市场突破扫描报告",
        f"扫描时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"数据库: 4804只股票 → 筛选≥{MIN_CONSOLIDATION_DAYS}天横盘 + ≥{MIN_VOLUME_EXPANSION}x量 + ≥{MIN_BREAKOUT_PCT}%突破",
        f"发现形态: {len(results)} 只",
        "",
        f"## 🏆 TOP {top_n}",
        "",
        "| 排名 | 代码 | 评分 | 横盘天 | 振幅% | 突破日 | 涨% | 量比 | 延伸% | 回踩 |",
        "|:---:|------|:---:|:---:|:---:|------|:---:|:---:|:---:|------|",
    ]

    for i, r in enumerate(results[:top_n]):
        pb_str = f"✅ ¥{r['pullback']['price']}" if r['pullback'] else "❌ 无"
        lines.append(
            f"| {i+1} | {r['code']} | {r['score']:.0f} | "
            f"{r['cons_days']} | {r['cons_range']} | {r['breakout_date']} | "
            f"{r['breakout_pct']} | {r['vol_expansion']}x | {r['ext_pct']} | "
            f"{pb_str} |"
        )

    lines.append("")
    lines.append("## 🎯 重点关注（有回踩信号的票）")
    pb_results = [r for r in results if r.get("pullback")]
    if pb_results:
        for r in pb_results[:15]:
            lines.append(f"### {r['code']} — 评分 {r['score']:.0f}")
            lines.append(f"- 横盘 {r['cons_days']}天，区间 ¥{r['cons_low']:.2f}-{r['cons_high']:.2f}，振幅 {r['cons_range']}%")
            lines.append(f"- 突破 {r['breakout_date']}，涨幅 {r['breakout_pct']}%，量比 {r['vol_expansion']}x")
            lines.append(f"- 回踩 ¥{r['pullback']['price']}（突破位{r['pullback']['pct']:+.1f}%），缩量至 {r['pullback']['vol_ratio']}x")
            lines.append(f"- 现价 ¥{r['latest']:.2f}，从底部涨 {r['ext_pct']}%")
            lines.append("")
    else:
        lines.append("⚠️ 无符合回踩条件的股票。")

    lines.append("---")
    lines.append(f"*扫描器 DB版 v1 · {datetime.now().strftime('%Y-%m-%d')}*")
    return "\n".join(lines)


def main():
    global MIN_CONSOLIDATION_DAYS
    args = sys.argv[1:]
    top_n = SCORE_TOP_N
    min_days = MIN_CONSOLIDATION_DAYS

    for i, arg in enumerate(args):
        if arg == "--top" and i + 1 < len(args):
            top_n = int(args[i+1])
        elif arg == "--min-days" and i + 1 < len(args):
            min_days = int(args[i+1])

    MIN_CONSOLIDATION_DAYS = min_days

    print(f"🔍 DB全量扫描启动...")
    print(f"   最小横盘: {min_days}天 | 最大振幅: {MAX_CONSOLIDATION_RANGE*100}% | 最小量比: {MIN_VOLUME_EXPANSION}x")

    stock_data = get_all_stocks_kline(DB_PATH, min_records=min_days + 10)
    if not stock_data:
        print("❌ 无可用数据")
        return

    results = scan_all(stock_data)
    print(f"\n✅ 扫描完成！发现 {len(results)} 个突破形态")

    report = format_report(results, top_n)
    print(report)

    os.makedirs(EVAL_DIR, exist_ok=True)
    path = os.path.join(EVAL_DIR, f"全市场突破扫描_{datetime.now().strftime('%Y%m%d')}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n✅ 报告已保存: {path}")


if __name__ == "__main__":
    main()
