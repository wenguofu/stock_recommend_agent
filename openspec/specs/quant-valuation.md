# Quantitative Valuation — 成长调整估值模型

> Added: 2026-05-30

## Purpose

For stocks already up 50%+, use fundamental analysis + industry growth projections to determine if the stock still has upside. Core insight: if industry profits double in 6 months, Forward PE is halved.

## Core Formulas

### Forward PE
`Forward PE = Current PE / (1 + industry_growth_rate)`

Example: PE=60, 6-month industry profit growth=100% → Forward PE = 60/2 = 30

### PEG Ratio
`PEG = PE / growth_rate%`

| PEG | Verdict |
|-----|---------|
| < 0.5 | Extremely undervalued |
| 0.5-1 | Reasonable — growth supports valuation |
| 1-2 | Fair |
| > 2 | Overvalued even after growth |

### Growth-Adjusted Fair Value
`Fair Value = EPS x Base PE x (1 + growth_adjustment)`

### DCF-Lite
3-year FCF projection (FCF = EPS x 0.7), WACC=10%, terminal growth=3%

### Composite Score (0-100)
Weighted: PEG(±25) + Margin of Safety(±15) + ROE(±10) + Sector Outlook(±10) + Forward PE(±10)

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/valuation/quick` | POST | Quick valuation with industry growth input |
| `/api/valuation/detail` | POST | Full parameter override |

## Frontend

`ValuationPanel.tsx` — Embedded in StockDetail page as "定量估值" tab. Input: stock code, 6m/1y industry growth %, sector name. Output: composite score ring, PEG, Forward PE, fair values, DCF, margin of safety.
