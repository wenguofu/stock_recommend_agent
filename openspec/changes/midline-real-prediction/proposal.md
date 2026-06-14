# Midline 真预判 + 移除敏感度扫描 UI

## Why

**问题 1 — 中线预判名不副实**: `/api/midline/watchlist-health` 端点返回值里只有健康度评分 (MA+MACD+RSI 0-100)，没有 forward-looking 预测。用户期望的"中线预判"应该是 1-4 周方向 + 概率 + 预期收益。现有 `dl_*` 字段用的是 short_term 模型 (1-5 日)，不是中线；而且 DL checkpoint 加载失败时**静默返回 None**，UI 显示"—"，让用户误以为"无预测"。

**问题 2 — 敏感度扫描页面对用户无价值**: `SensitivityScan.tsx` 是 Sprint5 给 AI 调参用的工具页面（扫描策略参数网格找最稳健区域），普通用户用不到，反而占着导航/命令面板/路由 4 个入口造成视觉噪音。

## What Changes

### 1. 中线真实预判（后端）
新增 `midline_routes.py` 三个内部函数 + 端点扩展：

- `_try_mid_term_dl(code)` — 调 `dl_models.mid_term_predictor` 加载 `mid_term_latest.pt`，跑 `predict(price_features, fund_features, regime)`，返回 `{mid_direction, mid_prob_up, mid_prob_down, mid_prob_flat, mid_expected_return, mid_horizon}`。失败返回 None。
- `_rule_based_midline_predict(score_dict)` — 规则 fallback:
  - 总分 ≥ 70 且 MACD 多头 → up (prob_up 0.65, 期望收益 +3%)
  - 总分 ≤ 30 OR MACD 死叉 → down (prob_down 0.55, 期望收益 −2%)
  - 其他 → flat (prob_up 0.50, 期望收益 0%)
- `midline_predict(code, dl_enabled=True)` — 编排: 优先 DL → 失败回落 rule-based → 再失败安全默认 (flat, 0.5)

`/api/midline/watchlist-health` 响应每只股票增加 7 个 `mid_*` 字段，`mid_model` 标记走的是 DL 还是规则。

### 2. 中线预判（前端）
`stock_frontend/src/pages/Midline.tsx` 自选池表格新增"中线预判"列（紧邻"DL预测"列），显示方向箭头 + 概率% + 模型标签 `[DL]` 或 `[规则]`，tooltip 显示期望收益。

### 3. 移除敏感度扫描 UI（保留后端）
- 删除 `stock_frontend/src/pages/SensitivityScan.tsx`
- `App.tsx` 去掉 import + `/sensitivity` 路由
- `Layout.tsx` 去掉导航项
- `CommandPalette.tsx` 去掉命令面板条目
- `tests/e2e/page_tests/sensitivity_scan.py` 删
- `tests/e2e/page_tests/__init__.py` 去掉引用
- **保留** `services/api.ts` 的 `scanSensitivity` / `getSensitivityDefaultGrid` 方法 + 后端 `/api/sensitivity/*` 端点 + `services/sensitivity_scan.py` 模块（AI 内部用，UI 不暴露）

## Out of Scope

- 不改 short-term 预测逻辑（已有 1-5 日预测，保留）
- 不重写中线健康度评分 (`_score_stock`)
- 不重写 mid_term DL 模型本身
- 不改 `services/sensitivity_scan.py` / `/api/sensitivity/*` 后端
- 不改 `tests/test_zisuye.py` / `tests/test_db.py` / 测试 fixture
- 不改 README 章节（次要，可后续小 PR 更新）

## Spec 变更

`openspec/specs/midline-trading.md` 暂无（midline 在 `paper-trading.md` 还是 `risk-ml.md` 里？查后定）。本 change 通过加 `## MODIFIED Requirements` 块到最相关的 spec（待定，先用 inline 描述）。

## 验收

1. `pytest tests/test_midline_predict.py` 10/10 通过
2. `pytest tests/test_engine_factory.py` 6/6 通过（确保未破坏引擎工厂）
3. `pytest tests/test_db.py tests/test_zisuye.py` 不引入新 fail（无 TEST_DATABASE_URL 时全 skip）
4. UI 检查：`/sensitivity` 路径返回 404，`Cmd+K` 找不到"敏感度扫描"，左侧导航无该项
5. 手动验证：起后端 + 前端，打开自选池健康度页，每行应看到新"中线预判"列，显示 `↑涨 65% [规则]` 或 `↑涨 72% [DL]` 之类
6. DL 不可用场景：即使 `model_checkpoints/mid_term_latest.pt` 缺失，每行仍有中线预判值（不显示"—"）
7. `openspec validate --strict` 通过
8. 文档：README.md 中线段说明 "DL 失败时静默 None" → "自动回落到规则概率 (1-4 周 outlook)"

## 风险

- **mid_term 模型在新数据上没验证**: checkpoint 在 `model_checkpoints/mid_term_latest.pt`，不知道最后训练时间；如果很久没训，预测可能漂移。fallback 在这种时候反而更稳。缓解: README 标注"模型需定期 retrain"
- **rule-based 参数拍脑袋**: 0.65 / 0.55 / 0.50 是经验值，需要后续 calibration。缓解: 函数命名带 `_rule_based_` 表明非 ML；UI 标 `[规则]`
- **删除 sensitivity_scan.py UI 可能被用户意外访问 /sensitivity 路径**: 路由已删，访问会 404，是预期行为
