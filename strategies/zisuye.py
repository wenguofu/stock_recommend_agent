#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
紫苏叶理论选股策略 (Shiso Leaf Theory)
========================================

来源: Serenity (@aleabitoreddit) — 紫苏叶理论

核心思想:
    在大产业链中, 找到那些小到没人愿意看、冷到没人愿意写、但一旦断供
    整条产业链就会卡住的"瓶颈点"。

    - 金枪鱼大腹 = 明星公司 (英伟达/中际旭创) — 显眼、贵、所有人都讨论
    - 紫苏叶     = 隐形瓶颈供应商 — 小市值、冷门、但卡住整条链

五问漏斗 (顺序不能反):
    1) 物理瓶颈在哪?
    2) 瓶颈唯一吗?
    3) 唯一性有商业化路径吗?        ← 第三问(商业化路径)由人类判断,
                                     录入 shiso_chokepoints.moat_note 字段,
                                     不直接喂入评分公式.
    4) 商业化路径有财务弹性吗?     ← 量化: 财务弹性 30%
    5) 市场有没有定价?             ← 量化: 定价错误 30%

评分卡 (满分100):
    行业地位  40%  (来自 shiso_chokepoints.monopoly_score / player_count)
    财务弹性  30%  (来自 stock_financials: revenue_yoy / profit_yoy / roe / gross_margin)
    定价错误  30%  (PE/PB 相对行业折价 + 流动性低 = 冷门溢价)
    额外加分  ±    (来自 shiso_chokepoints.extra_score, 0-±20)

风控 (默认):
    市值 ≤ 200 亿
    日成交额 ≥ 5000 万
    止损线 -5%
    +50% 减仓 1/3

输出:
    {
      'strategy': 'zisuye',
      'name': '紫苏叶',
      'description': ...,
      'count': N,
      'stocks': [{rank, code, name, price, score, chain_name, layer, ...}, ...]
    }
"""
import json
import os
import sys
from datetime import datetime
from typing import List, Dict, Optional

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import SessionLocal, StockFinancial
from sqlalchemy import text

from db import list_shiso_chokepoints, list_shiso_chains, save_shiso_picks


# ═══════════════════════════════════════════════════════════════
# 默认参数 (可被外部覆盖)
# ═══════════════════════════════════════════════════════════════

DEFAULTS = {
    "max_market_cap_yi": 200.0,   # 市值 ≤ 200 亿
    "min_amount_wan": 5000.0,     # 日成交额 ≥ 5000 万
    "stop_loss_pct": -5.0,        # 止损 -5%
    "trim_pct": 50.0,             # +50% 减仓
    "trim_size": 1.0 / 3,         # 减仓 1/3
    "top_n": 20,                  # 候选池大小
    "weights": {                  # 评分权重 (合计 100%)
        "industry": 0.40,
        "elasticity": 0.30,
        "mispricing": 0.30,
    },
}

_REQUIRED_WEIGHT_KEYS = {"industry", "elasticity", "mispricing"}


def _validate_weights(weights: dict) -> None:
    """校验 weights 字典结构, 缺键时给出明确错误而不是 KeyError 散落在循环里"""
    missing = _REQUIRED_WEIGHT_KEYS - set(weights or {})
    if missing:
        raise ValueError(f"zisuye weights 缺少键: {sorted(missing)}")


# ═══════════════════════════════════════════════════════════════
# 评分子项
# ═══════════════════════════════════════════════════════════════

def _score_industry(monopoly_score, player_count: int) -> float:
    """行业地位: 直接用 chokepoints.monopoly_score (0-100)

    玩家数越多, 越扣分 (竞争激烈):
        player_count == 1: +5  (垄断级, 加分)
        player_count == 2: +2  (双寡头 sweet spot, 适度加分)
        player_count == 3: -10
        player_count >= 4: -20

    None → 默认 50; 显式 0 → 尊重 0
    """
    score = 50.0 if monopoly_score is None else float(monopoly_score)
    if player_count <= 1:
        score += 5   # 垄断级, 加分
    elif player_count == 2:
        score += 2   # 双寡头 sweet spot (避免双寡头被压平)
    elif player_count == 3:
        score -= 10
    else:
        score -= 20
    return max(0, min(100, score))


def _score_elasticity(fin: dict) -> float:
    """财务弹性: 营收增速 + 利润增速 + ROE + 毛利率

    评分 (满分100):
        营收增速 YoY:
            >50%: +30, 30-50%: +25, 15-30%: +18, 0-15%: +10, <0: 0
        利润增速 YoY:
            >50%: +30, 20-50%: +22, 0-20%: +15, <0: 0
        ROE:
            >15%: +20, 10-15%: +15, 5-10%: +8, <5%: 0
        毛利率:
            >40%: +20, 25-40%: +15, 15-25%: +8, <15%: 0

    任一维度数据缺失, 对应子项给 0, 不影响其他子项
    """
    score = 0.0

    rev_yoy = fin.get("revenue_yoy")
    if rev_yoy is not None:
        if rev_yoy > 50:
            score += 30
        elif rev_yoy > 30:
            score += 25
        elif rev_yoy > 15:
            score += 18
        elif rev_yoy > 0:
            score += 10
        # < 0 不加分

    prof_yoy = fin.get("profit_yoy")
    if prof_yoy is not None:
        if prof_yoy > 50:
            score += 30
        elif prof_yoy > 20:
            score += 22
        elif prof_yoy > 0:
            score += 15
        # < 0 不加分

    roe = fin.get("roe")
    if roe is not None:
        if roe > 15:
            score += 20
        elif roe > 10:
            score += 15
        elif roe > 5:
            score += 8

    gm = fin.get("gross_margin")
    if gm is not None:
        if gm > 40:
            score += 20
        elif gm > 25:
            score += 15
        elif gm > 15:
            score += 8

    return max(0, min(100, score))


def _score_mispricing(fin: dict, turnover: float) -> float:
    """定价错误: PE/PB 相对行业 + 换手率 (冷门溢价)

    PE 折价: 相对行业 PE (pe_industry), 折价越多, 错杀概率越大
        <0.3: 30分 (极度低估)
        0.3-0.6: 22分
        0.6-1.0: 12分
        >1.0: 5分 (无折价)
        缺失: 0

    PB 折价: 相对行业 PB (pb_industry)
        <0.5: 25分
        0.5-1.0: 15分
        >=1.0: 5分
        缺失: 0

    冷门溢价: 换手率越低, 越被冷落, 错杀概率越大
        <1%: 45分 (极度冷门)
        1-3%: 30分
        3-8%: 15分
        >8%: 5分
        缺失: 0
    """
    score = 0.0

    pe_ttm = fin.get("pe_ttm")
    pe_ind = fin.get("pe_industry")
    if pe_ttm is not None and pe_ind is not None and pe_ind > 0 and pe_ttm > 0:
        ratio = pe_ttm / pe_ind
        if ratio < 0.3:
            score += 30
        elif ratio < 0.6:
            score += 22
        elif ratio < 1.0:
            score += 12
        else:
            score += 5

    pb = fin.get("pb")
    pb_ind = fin.get("pb_industry")
    if pb is not None and pb_ind is not None and pb_ind > 0 and pb > 0:
        ratio = pb / pb_ind
        if ratio < 0.5:
            score += 25
        elif ratio < 1.0:
            score += 15
        else:
            score += 5

    if turnover is not None:
        if turnover < 1:
            score += 45
        elif turnover < 3:
            score += 30
        elif turnover < 8:
            score += 15
        else:
            score += 5

    return max(0, min(100, score))


# ═══════════════════════════════════════════════════════════════
# 市值估算
# ═══════════════════════════════════════════════════════════════

def _estimate_market_cap_yi(price: float, amount: float, turnover: float) -> Optional[float]:
    """用 turnover 法估算市值 (亿)

    原理: turnover% = volume/shares, volume = amount/price
          shares = volume/(turnover/100) = amount/(price*turnover/100)
          market_cap = price * shares = amount * 100 / turnover
          换算成亿: amount * 100 / turnover / 1e8 = amount / turnover / 1e6

    Args:
        price:    当日收盘价(元)
        amount:   当日成交额(元)
        turnover: 当日换手率, 必须是**百分比数值** (2.5 表示 2.5%),
                  不可传 0.025 这种小数形式.

    Returns: 市值(亿), 数据缺失返回 None (调用方据此放行, 保守不误杀).
    """
    if not amount or not turnover or turnover <= 0 or price <= 0:
        return None
    market_cap_yuan = amount * 100.0 / turnover
    return market_cap_yuan / 1e8  # 转亿


# ═══════════════════════════════════════════════════════════════
# 主函数
# ═══════════════════════════════════════════════════════════════

def screen_zisuye(
    chain_name: str = None,
    top_n: int = DEFAULTS["top_n"],
    config: dict = None,
    require_verified: bool = False,
    customer: str = None,
) -> dict:
    """紫苏叶选股主函数

    Args:
        chain_name:      指定产业链, None = 全产业链
        top_n:           返回 TopN
        config:          覆盖默认参数, dict 形式
        require_verified: 是否要求 supply_chain_verified=True (供应链环节验证)
        customer:         指定终端客户 (如 'SpaceX'), None = 全部

    Returns:
        dict {strategy, name, description, count, stocks}
    """
    cfg = {**DEFAULTS, **(config or {})}
    weights = cfg["weights"]
    _validate_weights(weights)

    db = SessionLocal()
    try:
        # 1. 加载产业链 + 卡位候选
        chokepoints = list_shiso_chokepoints(
            db, chain_name=chain_name, enabled_only=True,
            require_verified=require_verified, customer=customer,
        )
        if not chokepoints:
            desc_parts = []
            if require_verified:
                desc_parts.append("require_verified=True")
            if customer:
                desc_parts.append(f"customer={customer}")
            desc = ", ".join(desc_parts) if desc_parts else ""
            return {
                "strategy": "zisuye",
                "name": "紫苏叶",
                "description": f"无卡位候选{f' ({desc})' if desc else ''}, 请先运行 seed_zisuye.py",
                "count": 0,
                "stocks": [],
                "config": cfg,
            }

        # 2. 候选 code → chokepoint 映射 (同一 code 多链时取 monopoly_score 最高的)
        cp_by_code: Dict[str, list] = {}
        for cp in chokepoints:
            cp_by_code.setdefault(cp.code, []).append(cp)

        codes = list(cp_by_code.keys())

        # 3. 拉取最新行情 (最近一天)
        placeholders = ",".join([f":c{i}" for i in range(len(codes))])
        params = {f"c{i}": codes[i] for i in range(len(codes))}
        latest_quote_rows = db.execute(text(f"""
            SELECT b.code, b.close, b.change_pct, b.turnover, b.amount, b.volume, b.date
            FROM backtest_data b
            INNER JOIN (
                SELECT code, MAX(date) AS max_date
                FROM backtest_data
                WHERE code IN ({placeholders})
                GROUP BY code
            ) m ON b.code = m.code AND b.date = m.max_date
        """), params).fetchall()

        quote_by_code = {r[0]: {
            "price": r[1],
            "change_pct": r[2],
            "turnover": r[3],
            "amount": r[4],
            "volume": r[5],
            "date": r[6],
        } for r in latest_quote_rows}

        # 4. 拉取最新财务数据 (每只取最近一期)
        fin_by_code = {}
        for code in codes:
            row = db.query(StockFinancial).filter(
                StockFinancial.code == code,
            ).order_by(StockFinancial.report_date.desc()).first()
            if row:
                fin_by_code[code] = {
                    "report_date": row.report_date,
                    "revenue_yoy": row.revenue_yoy,
                    "profit_yoy": row.profit_yoy,
                    "roe": row.roe,
                    "gross_margin": row.gross_margin,
                    "pe_ttm": row.pe_ttm,
                    "pb": row.pb,
                    "pe_industry": row.pe_industry,
                    "pb_industry": row.pb_industry,
                }

        # 5. 拉取股票名 (backtest_stock_meta)
        name_rows = db.execute(text(f"""
            SELECT code, name FROM backtest_stock_meta WHERE code IN ({placeholders})
        """), params).fetchall()
        name_by_code = {r[0]: r[1] for r in name_rows}

        # 6. 风控过滤 + 评分
        candidates = []
        for code, cp_list in cp_by_code.items():
            # 同一 code 多链时, 取 monopoly_score 最高的卡位
            cp = max(cp_list, key=lambda x: (x.monopoly_score or 0))
            quote = quote_by_code.get(code)
            fin = fin_by_code.get(code)

            # 风控: 必须有当日行情
            if not quote or not quote.get("price") or quote["price"] <= 0:
                continue
            if quote["price"] < 2:  # 垃圾股过滤
                continue

            # 风控: 成交额
            amount_wan = (quote.get("amount") or 0) / 1e4  # 元 → 万
            if amount_wan < cfg["min_amount_wan"]:
                continue

            # 风控: 市值
            market_cap_yi = _estimate_market_cap_yi(
                quote["price"], quote.get("amount"), quote.get("turnover"),
            )
            if market_cap_yi is not None and market_cap_yi > cfg["max_market_cap_yi"]:
                continue
            # 市值数据缺失时, 放行 (保守处理: 不误杀)

            # 三项评分
            industry = _score_industry(cp.monopoly_score, cp.player_count)
            elasticity = _score_elasticity(fin or {})
            mispricing = _score_mispricing(fin or {}, quote.get("turnover"))

            total = (
                industry * weights["industry"]
                + elasticity * weights["elasticity"]
                + mispricing * weights["mispricing"]
                + float(cp.extra_score or 0)
            )

            candidates.append({
                "code": code,
                "name": cp.name or name_by_code.get(code, ""),
                "price": round(float(quote["price"]), 2),
                "change_pct": round(float(quote.get("change_pct") or 0), 2),
                "turnover": round(float(quote.get("turnover") or 0), 2),
                "amount": round(float(quote.get("amount") or 0), 0),  # 成交额(元)
                "amount_wan": round(amount_wan, 0),
                "market_cap_yi": round(market_cap_yi, 1) if market_cap_yi else None,
                "chain_name": cp.chain_name,
                "layer": cp.layer,
                "moat": cp.moat_note,
                "industry_score": round(industry, 1),
                "elasticity_score": round(elasticity, 1),
                "mispricing_score": round(mispricing, 1),
                "extra_score": round(float(cp.extra_score or 0), 1),
                "total_score": round(total, 1),
                "stop_loss_pct": cfg["stop_loss_pct"],
                "trim_pct": cfg["trim_pct"],
                "trim_size": cfg["trim_size"],
                "report_date": fin.get("report_date") if fin else None,
                "reason": _build_reason(cp, industry, elasticity, mispricing),
            })

        # 7. 排序 + 排名
        candidates.sort(key=lambda x: x["total_score"], reverse=True)
        for i, c in enumerate(candidates, 1):
            c["rank"] = i
        top = candidates[:top_n]

        return {
            "strategy": "zisuye",
            "name": "紫苏叶",
            "description": (
                "产业链反推 + 行业地位/财务弹性/定价错误 三因子评分. "
                "筛选卡住整条链的小市值瓶颈供应商, 严控流动性."
            ),
            "count": len(top),
            "total_candidates": len(candidates),
            # 用全候选池统计, 避免被 topN 截断后链数被压低
            "chains_count": len({c["chain_name"] for c in candidates}),
            "stocks": top,
            "config": cfg,
        }
    finally:
        db.close()


def _build_reason(cp, industry, elasticity, mispricing) -> str:
    """生成入选理由"""
    parts = [f"卡位: {cp.layer or cp.chain_name}"]
    parts.append(f"垄断度 {cp.monopoly_score:.0f}/100, 全球玩家 {cp.player_count}")
    if cp.moat_note:
        parts.append(f"护城河: {cp.moat_note}")
    if industry >= 70:
        parts.append(f"行业地位强({industry:.0f})")
    if elasticity >= 60:
        parts.append(f"财务弹性优({elasticity:.0f})")
    if mispricing >= 60:
        parts.append(f"定价错误({mispricing:.0f})")
    return " | ".join(parts)


# ═══════════════════════════════════════════════════════════════
# 工具函数: 保存结果到 DB
# ═══════════════════════════════════════════════════════════════

def run_and_save(pick_date: str = None, chain_name: str = None, top_n: int = 20,
                 require_verified: bool = False, customer: str = None) -> dict:
    """跑批 + 持久化到 shiso_picks 表"""
    if pick_date is None:
        pick_date = datetime.now().strftime("%Y-%m-%d")

    result = screen_zisuye(chain_name=chain_name, top_n=top_n,
                           require_verified=require_verified, customer=customer)

    if result["stocks"]:
        db = SessionLocal()
        try:
            save_shiso_picks(db, pick_date=pick_date, picks=result["stocks"])
        finally:
            db.close()

    return result


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="紫苏叶选股策略")
    p.add_argument("--chain", default=None, help="指定产业链, 默认全部")
    p.add_argument("--top", type=int, default=20, help="返回 TopN")
    p.add_argument("--save", action="store_true", help="保存到 shiso_picks 表")
    p.add_argument("--require-verified", action="store_true",
                   help="仅返回 supply_chain_verified=True 的卡位")
    p.add_argument("--customer", default=None,
                   help="指定终端客户 (如 'SpaceX' / 'NVIDIA')")
    p.add_argument("--date", default=None, help="选股日期, 默认今天")
    args = p.parse_args()

    if args.save:
        out = run_and_save(pick_date=args.date, chain_name=args.chain, top_n=args.top,
                           require_verified=args.require_verified, customer=args.customer)
    else:
        out = screen_zisuye(chain_name=args.chain, top_n=args.top,
                            require_verified=args.require_verified, customer=args.customer)
    print(json.dumps(out, ensure_ascii=False, indent=2))