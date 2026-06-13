"""K 线形态检测 — 5 类基础形态

返回 [{date, type, direction, note}, ...]
类型枚举与 frontend spec (specs/frontend/spec.md:67-72) 完全对齐,
前端 markPoint 颜色映射依赖此契约.
"""
from typing import List, Dict


def detect_patterns(klines: List[Dict]) -> List[Dict]:
    """检测 K 线形态 (5 类)

    - gap_up: 今日 low > 昨 high * 1.01
    - gap_down: 今日 high < 昨 low * 0.99
    - doji: |close-open| / (high-low) < 0.1
    - upper_shadow: (high - max(open,close)) / (high-low) > 0.6
    - lower_shadow: (min(open,close) - low) / (high-low) > 0.6
    """
    out: List[Dict] = []
    for i, k in enumerate(klines):
        if i == 0:
            continue
        prev = klines[i - 1]
        # 跳空缺口
        if k["low"] > prev["high"] * 1.01:
            out.append({
                "date": k["date"],
                "type": "gap_up",
                "direction": "up",
                "note": "向上跳空缺口",
            })
        elif k["high"] < prev["low"] * 0.99:
            out.append({
                "date": k["date"],
                "type": "gap_down",
                "direction": "down",
                "note": "向下跳空缺口",
            })

        body = abs(k["close"] - k["open"])
        rng = k["high"] - k["low"]
        if rng > 0:
            # 十字星
            if body / rng < 0.1:
                out.append({
                    "date": k["date"],
                    "type": "doji",
                    "direction": "neutral",
                    "note": "十字星",
                })
            # 长上影
            upper = k["high"] - max(k["open"], k["close"])
            if upper / rng > 0.6:
                out.append({
                    "date": k["date"],
                    "type": "upper_shadow",
                    "direction": "down",
                    "note": "长上影线",
                })
            # 长下影
            lower = min(k["open"], k["close"]) - k["low"]
            if lower / rng > 0.6:
                out.append({
                    "date": k["date"],
                    "type": "lower_shadow",
                    "direction": "up",
                    "note": "长下影线",
                })
    return out