# Tasks — Midline 真预判 + 移除敏感度扫描 UI

## 1. TDD Red
- [x] 1.1 `tests/test_midline_predict.py::TestRuleBasedMidlinePredict::test_high_health_with_bullish_macd_is_bullish`
- [x] 1.2 `tests/test_midline_predict.py::TestRuleBasedMidlinePredict::test_low_health_is_bearish`
- [x] 1.3 `tests/test_midline_predict.py::TestRuleBasedMidlinePredict::test_death_cross_is_bearish_even_with_mid_health`
- [x] 1.4 `tests/test_midline_predict.py::TestRuleBasedMidlinePredict::test_neutral_health_is_flat`
- [x] 1.5 `tests/test_midline_predict.py::TestRuleBasedMidlinePredict::test_probs_sum_to_one`
- [x] 1.6 `tests/test_midline_predict.py::TestMidlinePredictDlPath::test_dl_success_uses_mid_term_dl_model`
- [x] 1.7 `tests/test_midline_predict.py::TestMidlinePredictDlPath::test_dl_disabled_uses_rule_based`
- [x] 1.8 `tests/test_midline_predict.py::TestMidlinePredictFallback::test_dl_returns_none_falls_back_to_rule_based`
- [x] 1.9 `tests/test_midline_predict.py::TestMidlinePredictFallback::test_dl_raises_exception_also_falls_back`
- [x] 1.10 `tests/test_midline_predict.py::TestMidlinePredictFallback::test_rule_based_also_failing_returns_safe_default`

## 2. TDD Green
- [x] 2.1 `midline_routes.py::_try_mid_term_dl` — DL 加载 + predict
- [x] 2.2 `midline_routes.py::_rule_based_midline_predict` — 规则 fallback
- [x] 2.3 `midline_routes.py::midline_predict` — 编排 (DL → rule-based → safe default)
- [x] 2.4 `midline_routes.py::midline_watchlist_health` 端点返回 `mid_*` 字段
- [x] 2.5 跑 `pytest tests/test_midline_predict.py` 10/10 通过

## 3. 移除敏感度扫描 UI
- [x] 3.1 `stock_frontend/src/pages/SensitivityScan.tsx` 删除
- [x] 3.2 `stock_frontend/src/App.tsx` 删 import + `<Route path="/sensitivity">`
- [x] 3.3 `stock_frontend/src/components/Layout.tsx` 删导航项
- [x] 3.4 `stock_frontend/src/components/CommandPalette.tsx` 删命令项
- [x] 3.5 `tests/e2e/page_tests/sensitivity_scan.py` 删除
- [x] 3.6 `tests/e2e/page_tests/__init__.py` 删引用

## 4. 前端 mid_pred 列
- [x] 4.1 `Midline.tsx::HealthItem` interface 加 `mid_*` 字段
- [x] 4.2 `Midline.tsx` watchlist-health 表格加 "中线预判" 列（方向+概率+模型标签）

## 5. 验证
- [x] 5.1 `pytest tests/test_midline_predict.py` 10/10
- [x] 5.2 `pytest tests/test_engine_factory.py` 6/6 (无破坏)
- [x] 5.3 `pytest tests/test_db.py tests/test_zisuye.py` 全部 pass 或 skip
- [ ] 5.4 `openspec validate --strict` 通过
- [ ] 5.5 `grep -rn "SensitivityScan\|/sensitivity" stock_frontend/src/ tests/e2e/` 无命中
- [ ] 5.6 `ls stock_frontend/src/pages/SensitivityScan.tsx tests/e2e/page_tests/sensitivity_scan.py` 无输出

## 6. 归档
- [ ] 6.1 `opsx:archive midline-real-prediction`
