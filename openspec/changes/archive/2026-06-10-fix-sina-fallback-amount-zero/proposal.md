# Fix Sina Fallback 写 amount=0/turnover=0 Bug

## Why

`batch_prefetch_all.py` 的 Sina 兜底分支把 `amount` 和 `turnover` 硬编码为 0 写入 `backtest_data` 表（[batch_prefetch_all.py:186](batch_prefetch_all.py#L186)、[L188](batch_prefetch_all.py#L188)）。

当 `is_trading_time=False`（盘后、节假日、非交易时段）时，akshare 走不通，fallback 到 Sina，但 Sina K-line 接口只返回 `{day, open, high, low, close, volume}`，`_sina_to_records` 把 `amount` 和 `turnover` 硬置 0。

**下游影响（实际案例 2026-06-10）**：
- 紫苏叶策略 zisuye 选了 15 个 chokepoint，amount 全部=0
- 风控"成交额 ≥ 5000 万"过滤全挂，candidates=0（"选的股数据都落后太多"）
- 量化估值、推荐列表也用 amount/turnover 算市值/估值，全线失分

## What Changes

- **修复 `_sina_to_records`**：从已有字段推算 amount/turnover
  - amount = close × volume（Sina volume 单位是"股"）
  - turnover: 留 0 标记 "Sina 源不可得"，由后续增量补丁（腾讯快照）补齐
- **修复 `fetch_stock_data` 的非交易时段判断**：默认 9:30-11:30 / 13:00-15:00，**不**包括盘后 15:00-15:30（盘后仍能拉当日数据）
- **加 `enrich_with_tencent_snapshot`**：批量拉完后用 `qt.gtimg.cn` 补 turnover + 校验 amount（只对 amount=0 或 turnover=0 的行回填）
- **数据契约 spec**：`get_daily_kline` 返回值补 `amount`, `turnover` 字段

## Spec 变更

[market-data.md](../../specs/market-data.md) L10：
- `get_daily_kline(code, count)` 返回结构 `[{day,open,high,low,close,volume}]` → `[{day,open,high,low,close,volume,amount,turnover}]`
- L48: 腾讯字段索引保持
- L37-38: 注明 "Sina 源 amount/turnover 由 close×volume 推算 + 腾讯快照补 turnover"

## Out of Scope

- 不改 `fill_missing_data.py`（东方财富 push2his 当前 RemoteDisconnected，已知问题）
- 不改 `_df_to_records` (akshare 路径，amount/turnover 正常)
- 不动 zisuye 业务逻辑（spec 内的"市值≤200亿"风控保留）

## 验收

1. `pytest -q tests/test_batch_prefetch_sina.py` 全绿
2. 重跑 zisuye 拿 2026-06-10 数据：candidates 不再因 amount=0 全部过滤
3. `openspec validate --strict` 通过
