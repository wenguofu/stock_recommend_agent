# Tasks — AI Trading System Optimization

## Phase 1: DL Prediction Layer
- [x] Install PyTorch, ONNX, loguru
- [x] Create dl_models package with feature engineering (20 daily features)
- [x] RegimeDetector — Transformer bull/bear/sideways classifier
- [x] ShortTermPredictor — BiLSTM+Attention 1-5d prediction
- [x] MidTermPredictor — Transformer 1-4w prediction
- [x] Probability calibration (temperature scaling + isotonic regression)
- [x] ONNX export utilities
- [x] Integrate DL models with existing ml_predictor.py

## Phase 2: LLM Agent Decision Layer
- [x] Structured JSON output in ai_service.py
- [x] TradingAgent base class + 5 prompt templates
- [x] Agent orchestrator with concurrent execution and caching

## Phase 3: Risk Control Layer
- [x] Hard constraints validator (7 checks)
- [x] Circuit breaker + position guard

## Phase 4: Pipeline & Feedback
- [x] Daily pipeline orchestration (6 stages)
- [x] Performance tracker + auto-tuning weight optimizer

## Phase 5: Frontend Components
- [x] RegimeIndicator component
- [x] AgentReasoning component
- [x] ValuationPanel component + StockDetail integration

## Phase 6: Midline Panel Upgrades
- [x] DL prediction column in health table
- [x] Risk constraint validation in position calculator
- [x] Inline journal entry form (replace Modal)
- [x] Server-side pagination for watchlist/health/journal

## Phase 7: E2E & Polish
- [x] Register pipeline tasks in scheduler
- [x] E2E tests (18 tests passing)
- [x] TypeScript build fixes
- [x] Restart and verify
