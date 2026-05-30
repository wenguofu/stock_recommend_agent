# Risk & ML — 风险管理与机器学习

## 风险管理 (risk_management.py + risk_routes.py)

### 指标体系

| 指标 | 方法 | 输出 |
|------|------|------|
| VaR 95% | 历史模拟 + 参数法(正态) | 日最大亏损% |
| CVaR 95% | 尾部期望损失 | 超VaR平均损失 |
| 最大回撤 | 峰值-谷值 | % + 金额 |
| 夏普比率 | (日均收益-Rf)/σ × √252 | 风险调整收益 |
| 凯利仓位 | (pW - qL)/(W×L) | 最优仓位%(半凯利) |
| ATR 止损 | 14日ATR × 2.0 | 建议止损价 |
| 组合β | Cov(rp, rb)/Var(rb) | vs 沪深300 |

### API

| 端点 | 用途 |
|------|------|
| `POST /api/risk/report` | 个股综合风险报告 |
| `POST /api/risk/quick_summary` | AI prompt 注入文本 |
| `POST /api/risk/position_size` | 凯利仓位计算 |
| `POST /api/portfolio/correlation` | 组合相关性矩阵 |
| `POST /api/portfolio/optimize` | 均值-方差优化 |
| `POST /api/portfolio/efficient_frontier` | 有效前沿 |
| `POST /api/portfolio/risk_parity` | 风险平价 |
| `POST /api/portfolio/recommend` | 组合推荐 |

## ML 预测 (ml_predictor.py + factor_engine.py)

### 方法

| 方法 | 库 | 参数 |
|------|-----|------|
| RandomForest (主) | sklearn | depth=2, n=100, leaf=10 |
| 规则引擎 (降级) | 纯Python | 对称双向评分 |

### RF 最优参数 (80股 walk-forward 验证)

```python
RF_PARAMS = {
    'n_estimators': 100, 'max_depth': 2,
    'min_samples_leaf': 10, 'max_features': 'sqrt',
    'class_weight': 'balanced'
}
```

准确率: 52.17% (vs 规则 47.4%)

### 21因子体系 (factor_engine.py v2)

6大类: 动量(5) / 技术(4) / 资金(3) / 价值(3) / 质量(3) / 风险(3)

### API

| 端点 | 用途 |
|------|------|
| `POST /api/ml/predict/<code>` | 方向+收益率预测 |
| `POST /api/ml/direction/<code>` | 仅方向 |
| `POST /api/ml/return/<code>` | 仅收益率 |
| `GET /api/ml/predict_text/<code>` | AI prompt 注入 |
| `GET /api/factor/exposure/<code>` | 因子暴露分析 |
| `GET /api/factor/rating/<code>` | 21因子评分(A-E) |
| `POST /api/signal/fuse` | 7源信号融合 |

### 已知问题

- [ ] RF 训练数据基于单股自身历史(非横截面)，泛化能力受限
- [ ] sklearn 不可用时降级到规则引擎，静默切换无告警
- [ ] 预测有中性区间，但UI未明确展示置信度边界

## DL Prediction (dl_models/)

> Added: 2026-05-30 — Replaces shallow RF/Ridge with deep learning models

### Models

| Model | Architecture | Horizon | Input | Output |
|-------|-------------|---------|-------|--------|
| RegimeDetector | 2-layer Transformer | 60-day lookback | Market indices + breadth + volume | bull/bear/sideways + confidence |
| ShortTermPredictor | BiLSTM(2-layer) + MultiHeadAttention | 30-day seq | 20 daily features + regime context | direction(up/down/flat) + expected return(μ,σ) |
| MidTermPredictor | 4-layer Transformer | 52-week seq | 8 price features + 6 fundamental + regime | direction + expected return(μ,σ) |

### Feature Engineering (dl_models/features.py)

20 daily features: ret_1d, ret_3d, ret_5d, ret_10d, ret_20d, volatility_20d, ma_dev_5d/10d/20d/60d, rsi_14, atr_ratio, volume_ratio, bollinger_pos, amplitude, consecutive_up, consecutive_down, money_flow_5d, money_flow_10d, turnover_rate

### Calibration

- Temperature scaling (optimize single T via NLL)
- Isotonic regression (per-class, sklearn)
- ONNX export for all 3 models

### Integration

- `factor_engine.get_feature_vector()` — DL-ready numpy arrays from K-line data
- `ml_predictor.predict_with_dl()` — DL inference with RF fallback
- Model checkpoints in `model_checkpoints/` directory
- Daily retrain via pipeline (walk-forward validation)
