"""简易 DCF 估值 — 5 年显式 + Gordon 永续

命名约定 (canonical, short):
  - 入参: eps, current_price, growth, discount, terminal
  - 返回: {fair_value_per_share, current_price, upside_pct, assumptions}
  - 错误: {"error": "EPS 必须 > 0 且折现率 > 永续增速"}
"""
from typing import Optional


def dcf_valuation(
    eps: float,
    current_price: float,
    growth: float = 0.15,
    discount: float = 0.10,
    terminal: float = 0.03,
    years: int = 5,
) -> dict:
    """5 年显式预测 + Gordon Growth 永续

    公式:
      NPV_t = EPS_t × (1+g)^t / (1+r)^t   for t=1..N
      TV    = EPS_N × (1+g_t) / (r - g_t)
      TV_pv = TV / (1+r)^N
      fair  = sum(NPV_t) + TV_pv
    """
    if not eps or eps <= 0:
        return {"error": "EPS 必须 > 0 且折现率 > 永续增速"}
    if not discount or discount <= terminal:
        return {"error": "EPS 必须 > 0 且折现率 > 永续增速"}

    cashflows = []
    for t in range(1, years + 1):
        cf = eps * (1 + growth) ** t / (1 + discount) ** t
        cashflows.append(cf)

    terminal_value = (
        eps * (1 + growth) ** years * (1 + terminal)
        / (discount - terminal)
    )
    terminal_pv = terminal_value / (1 + discount) ** years

    fair = sum(cashflows) + terminal_pv

    upside_pct = None
    if current_price and current_price > 0:
        upside_pct = round((fair - current_price) / current_price * 100, 2)

    return {
        "fair_value_per_share": round(fair, 2),
        "current_price": current_price,
        "upside_pct": upside_pct,
        "assumptions": {
            "growth": growth,
            "discount": discount,
            "terminal": terminal,
            "years": years,
        },
    }