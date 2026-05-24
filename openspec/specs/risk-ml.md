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
