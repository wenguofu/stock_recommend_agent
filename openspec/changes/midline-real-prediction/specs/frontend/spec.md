# frontend delta — Midline 真预判 UI 契约

## MODIFIED Requirements

### Requirement: Midline 自选池表格必须显示中线预判列

`/api/midline/watchlist-health` 端点响应每行 MUST 包含 7 个 `mid_*` 字段，前端 `Midline.tsx` MUST 渲染独立的"中线预判"列（紧邻"DL预测"列右侧）。

#### Scenario: 响应包含 mid_* 字段

- **WHEN** 调 `GET /api/midline/watchlist-health?page=1&pageSize=20`
- **THEN** 每行 MUST 包含 7 字段: `mid_direction` / `mid_prob_up` / `mid_prob_down` / `mid_prob_flat` / `mid_expected_return` / `mid_horizon` / `mid_model`
- **AND** `mid_horizon` MUST 为 `"4w"`（1-4 周 outlook）
- **AND** `mid_model` MUST 为 `"mid_term_dl"` 或 `"rule_based"` 之一

#### Scenario: DL 可用时 mid_model = mid_term_dl

- **WHEN** `model_checkpoints/mid_term_latest.pt` 存在 + factor_engine 可产出 30 日 features
- **THEN** 端点 MUST 调 `dl_models.mid_term_predictor.MidTermPredictor.load()` 并用 `.predict()` 出方向/概率
- **AND** `mid_model` 标记为 `"mid_term_dl"`
- **AND** `mid_prob_up + mid_prob_down + mid_prob_flat` MUST 约等于 1.0 (误差 < 0.01)

#### Scenario: DL 失败时 fallback 到 rule_based, 字段不空

- **WHEN** DL checkpoint 缺失 / 加载失败 / torch 缺失 / feature 不足
- **THEN** 端点 MUST 回落 `_rule_based_midline_predict(score_dict)` 输出
- **AND** `mid_model` 标记为 `"rule_based"`
- **AND** mid_* 字段 MUST 仍有值 (不允许 null/None)
- **AND** 前端 MUST 显示"中线预判"列, 不显示"—"占位

#### Scenario: 中线预判列渲染

- **WHEN** 表格行 `mid_direction = "up"`, `mid_prob_up = 0.65`
- **THEN** 前端 MUST 显示 `↑涨 65% [规则]` 或 `↑涨 65% [DL]` (取决 mid_model)
- **AND** 颜色: up = 红色 (#cf1322), down = 蓝色 (#1677ff), flat = 灰色 (#999)
- **AND** tooltip MUST 显示"中线(4w) 预期收益: X.XX% | 模型: DL/规则"
