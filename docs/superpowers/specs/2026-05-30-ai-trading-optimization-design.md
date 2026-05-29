# AI Stock Trading System Optimization — Design Spec

**Date**: 2026-05-30
**Status**: Design Approved
**Approach**: Hybrid Ensemble (DL Prediction + LLM Agent Decision + Two-Layer Risk Control)

---

## 1. Overview & Goals

Optimize the existing A-stock trading system with a dual-layer AI architecture: Deep Learning for probabilistic price prediction and LLM Agents for information synthesis and trading decisions. Target: aggressive absolute returns (20-50%+ annualized) with high win rate and profit factor, via multi-horizon adaptive trading.

### Success Metrics
- Win rate > 60% (statistically significant via Wilson CI)
- Profit factor > 1.5 (avg win / avg loss)
- Sharpe ratio > 1.5 on paper trading
- Max drawdown < 20% (enforced by hard constraints)

---

## 2. System Architecture

```
Data Pipeline (daily post-close)
    │
    ▼
DL Prediction Layer
    ├── Market Regime Detector (Transformer, 3-class: bull/bear/sideways)
    ├── Short-term Predictor (LSTM+Attention, 1-5 day direction+return+uncertainty)
    └── Mid-term Predictor (Transformer, 1-4 week direction+return+uncertainty)
    │  Structured JSON predictions with confidence intervals
    ▼
LLM Agent Decision Layer
    ├── Macro Agent (market context, sector rotation, policy)
    ├── Technical Agent (DL signal interpretation, factor scores, patterns)
    ├── Fundamental Agent (valuation, earnings quality, growth)
    ├── Risk Agent (VaR, drawdown, position sizing, veto power)
    └── Fusion Agent (synthesizes all 4, outputs final decision)
    │  Structured decision: {action, position_pct, stop_loss, take_profit}
    ▼
Two-Layer Risk Control
    ├── Layer 1 (Soft): Risk reasoning embedded in Agent decision-making
    └── Layer 2 (Hard): Pre-execution constraint enforcement
    │
    ▼
Execution + Feedback Loop
    Paper trading → Track recommendations → Evaluate performance → Auto-tune weights
```

---

## 3. DL Prediction Layer

### 3.1 Market Regime Detector
- **Model**: 2-layer Transformer Encoder (d_model=128, heads=4)
- **Input**: 60-day index sequences (CSI 300, CSI 500, ChiNext), market breadth, volume trend, north-bound flow, sector dispersion
- **Output**: 3-class (bull/bear/sideways) + per-class probability
- **Labels**: Post-hoc labeling (future 20d return >10%→bull, <-10%→bear, else→sideways)
- **Training**: Monthly walk-forward, class_weight balancing

### 3.2 Short-term Predictor (1-5 days)
- **Model**: 2-layer BiLSTM (hidden=128) + MultiHeadAttention (4 heads)
- **Input**: 30-day daily K-line sequences, technical indicators (RSI, MACD, Bollinger, ATR), money flow (5d/10d net inflow, large order ratio), volume/price features, regime context encoding
- **Output**: Direction (up/down/flat) probabilities + expected return (μ, σ) via Gaussian NLL
- **Training**: Daily retrain with incremental data, strict temporal walk-forward

### 3.3 Mid-term Predictor (1-4 weeks)
- **Model**: 4-layer Transformer Encoder (d_model=256, heads=8)
- **Input**: 52-week weekly K-line sequences, fundamentals (PE percentile, PB, ROE, gross margin, revenue growth, debt ratio), 20d money flow trend, sector strength ranking, regime context
- **Output**: Same dual-head as short-term (direction + return with uncertainty)
- **Training**: Daily retrain with walk-forward validation

### 3.4 Model Infrastructure
- **Framework**: PyTorch (training) + ONNX (inference)
- **Versioning**: File-based `model_vYYYYMMDD.pt`, retain 30 days
- **Calibration**: Temperature scaling + isotonic regression post-hoc
- **GPU**: Optional, CPU sufficient for current data scale

---

## 4. LLM Agent Decision Layer

### 4.1 Agent Architecture
Four specialist agents run in parallel, one fusion agent runs sequentially:

| Agent | Role | Key Inputs | Output |
|-------|------|------------|--------|
| Macro | Senior macro strategist | Index data, sector heatmap, north-bound flow, policy news, regime prediction | Market stance (bullish/neutral/bearish), top 3 strong/weak sectors, confidence 0-100 |
| Technical | Quantitative technical analyst | DL predictions (short+mid), factor scores, pattern recognition, volume/price anomalies | Technical stance, key signals, signal conflicts, confidence 0-100 |
| Fundamental | Value investment analyst | PE/PB percentiles, ROE trends, revenue/profit growth, industry comparison | Valuation assessment, catalyst/risk points, confidence 0-100 |
| Risk | Risk management expert | VaR/CVaR, max drawdown, volatility, correlation, Kelly sizing, liquidity | Risk grade, position cap recommendation, veto flag, confidence 0-100 |

### 4.2 Fusion Agent Rules
1. Risk Agent has veto power — cannot buy when risk grade is "high"
2. Buy requires ≥2 of (Macro, Technical, Fundamental) bullish AND none bearish
3. If any 2 agents have confidence < 40, downgrade to "hold" or "watch"
4. Conflicting signals: prefer the lower-risk option
5. Position size = Kelly × risk_coefficient × regime_coefficient

### 4.3 Structured Output
```json
{
  "action": "buy|sell|hold|watch",
  "confidence": 0-100,
  "position_pct": 0-20,
  "stop_loss_pct": -8,
  "take_profit_pct": 25,
  "reasoning": "One-line decision summary",
  "risk_flags": ["high_volatility", "earnings_window"],
  "horizon": "short|mid"
}
```

### 4.4 Technical Implementation
- **Parallel execution**: 4 agents called concurrently, fusion agent sequential
- **Model**: DeepSeek (default, cost-effective), higher-capability models for high-conviction decisions
- **Structured output**: `response_format=json_object` with JSON Schema
- **Caching**: Same stock + same data window cached for 1 hour
- **Pre-screening**: DL pre-filters top 50 stocks before agent analysis
- **Cost**: ~0.01-0.02 USD per stock full analysis (~32K tokens)

---

## 5. Two-Layer Risk Control

### 5.1 Layer 1: Soft Risk (Agent-Embedded)
Risk Agent's system prompt includes current portfolio state, position concentrations, recent P&L, and risk limits. The agent naturally incorporates risk reasoning into its output. The Fusion Agent applies the risk coefficient to position sizing.

### 5.2 Layer 2: Hard Constraints (Pre-Execution)

| Constraint | Threshold | Action |
|------------|-----------|--------|
| Single position cap | ≤ 20% | Block/auto-reduce |
| Total exposure cap | ≤ 80% | Block buys, suggest reducing first |
| Daily loss circuit breaker | -5% | No new positions, only stop-loss allowed |
| Sector concentration | ≤ 30% | Block same-sector additions |
| Portfolio VaR limit | ≤ 2% of total assets | Scale down until satisfied |
| Liquidity check | Daily turnover ≥ 50M CNY | Exclude illiquid stocks |
| Stop-loss discipline | ATR 2x or -8% (tighter wins) | Auto-place stop order |

---

## 6. Data Pipeline & Daily Workflow

```
15:05 — Data Fetch: full-market K-line (incremental), sector data, money flow, fundamentals
15:15 — Feature Engineering: 60-day rolling windows, 20 factors, multi-horizon alignment
15:30 — DL Training: regime detector → short-term LSTM → mid-term Transformer → ONNX export
16:00 — Market-wide DL Screening: ~5000 stocks → regime filter → top 100 by prediction score
16:30 — LLM Agent Analysis: top 30 of 100 → 4-agent concurrent (semaphore≤5 concurrent) → fusion
17:30 — Generate Recommendations: write to DB, update dashboard, optional push notification
```

Scheduled via the existing `scheduler.py`, extended with pipeline orchestration.

---

## 7. Feedback Loop & Auto-Tuning

### 7.1 Performance Tracking
Each recommendation tracked at T+1, T+3, T+5 (short-term expiry), T+20 (mid-term expiry). Metrics by source:
- Win rate (Wilson confidence interval)
- Profit factor (avg win / avg loss)
- Expected return (win_rate × avg_win - loss_rate × avg_loss)
- Information Coefficient (corr(predicted_direction, actual_direction))
- Statistical significance (binomial test p-value)

### 7.2 Monthly Auto-Tuning
Compare recent performance across all signal sources. Adjust fusion weights by ±5-10% based on relative IC and win rate. Risk Agent's veto power maintained if veto accuracy > 70%.

---

## 8. Integration with Existing System

| Existing Module | Change Strategy | Impact |
|-----------------|-----------------|--------|
| `factor_engine.py` | Retain & enhance — feed factors into DL feature vectors | Low |
| `ml_predictor.py` | Refactor — RF/Ridge → DL model inference, keep fallback | Medium |
| `ai_service.py` | Extend — add structured output (JSON mode) | Low |
| `signal_fusion.py` | Refactor — hardcoded weights → dynamic tuning + LLM fusion | High |
| `risk_management.py` | Extend — add hard constraints, circuit breaker, sector check | Medium |
| `debate_routes.py` | Refactor — split 49K-line file, extract agent templates | High |
| `recommendation_tracker.py` | Extend — multi-dimension tracking, auto weight tuning | Medium |
| `paper_trading.py` | Extend — integrate hard constraint enforcement, auto stop-loss | Medium |
| `scheduler.py` | Extend — daily pipeline orchestration | Medium |
| `stock_frontend/` | Add pages — regime indicator, agent reasoning chains, feedback dashboard | Medium |

---

## 9. New Module Structure

```
dl_models/
  ├── regime_detector.py        # Market regime classifier
  ├── short_term_predictor.py   # BiLSTM+Attention model
  ├── mid_term_predictor.py     # Transformer model
  ├── features.py               # DL feature engineering
  ├── calibration.py            # Probability calibration
  └── onnx_export.py            # PyTorch→ONNX export

llm_agents/
  ├── agent_base.py             # Agent base class (API call, structured output, retry)
  ├── agent_prompts/            # System prompt templates (per agent)
  ├── agent_orchestrator.py     # 4-agent concurrent + fusion orchestration
  └── agent_cache.py            # Analysis result cache

risk_control/
  ├── hard_constraints.py       # Hard constraint interceptor
  ├── circuit_breaker.py        # Daily loss circuit breaker
  └── position_guard.py         # Position + sector concentration guard

feedback/
  ├── performance_tracker.py    # Multi-dimension performance tracking
  └── weight_optimizer.py       # Auto-tuning engine

pipeline/
  └── daily_pipeline.py         # Daily post-close pipeline orchestration
```

---

## 10. New Dependencies

- **PyTorch** (≥2.0): DL model training + inference
- **onnx / onnxruntime**: Model export + efficient inference
- **loguru**: Structured logging (replaces scattered `print` statements)
- Existing dependencies (scikit-learn, pandas, numpy) remain unchanged

---

## 11. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| DL models overfit on limited data | Strict walk-forward validation, probability calibration, keep RF fallback |
| LLM hallucinations in trading decisions | Structured JSON output, risk agent veto, hard constraints as safety net |
| Pipeline runtime exceeds window | CPU inference for DL screening is fast; cap agent analysis at 30 stocks; make parallelizable |
| Data quality from free APIs | Accept imperfection; model uncertainty quantification handles noise; add paid data incrementally |
| System complexity too high to debug | Modular design with clear interfaces; each component independently testable |

---

## 12. Implementation Phases (Overview)

1. **Phase 1**: DL Prediction Layer (regime detector + short-term + mid-term models, feature engineering, ONNX export)
2. **Phase 2**: LLM Agent Decision Layer (agent prompts, orchestrator, structured output, caching)
3. **Phase 3**: Risk Control Layer (hard constraints, circuit breaker, position guard)
4. **Phase 4**: Pipeline & Feedback (daily automation, performance tracking, auto-tuning)
5. **Phase 5**: Frontend (regime indicator, agent reasoning UI, feedback dashboard)
6. **Phase 6**: Integration & Testing (end-to-end paper trading validation, walk-forward backtest)

Detailed task breakdown deferred to implementation plan.
