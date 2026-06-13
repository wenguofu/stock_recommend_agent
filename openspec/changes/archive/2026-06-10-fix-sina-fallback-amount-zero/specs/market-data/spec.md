# market-data delta — Sina fallback amount/turnover

## MODIFIED Requirements

### Requirement: get_daily_kline 返回结构

`get_daily_kline(code, count)` 拉取日 K 线数据时, 返回的每条记录 **MUST** 包含成交额/换手率字段, 以支撑下游风控(成交额过滤)、估值(市值估算)、推荐评分.

#### Scenario: akshare 源返回完整字段

- **WHEN** 当前在 A 股交易时段(9:30-11:30 / 13:00-15:00)且 akshare 可用
- **THEN** 返回的每条记录应包含 `amount` (成交额, 元) 和 `turnover` (换手率, %, 0-100 数值)
- **AND** `source` 标记为 `"akshare"`

#### Scenario: Sina fallback 源 amount 推算

- **WHEN** 当前在非交易时段或 akshare 不可用, 走 Sina K-line 兜底
- **THEN** 返回的每条记录 **MUST** 包含 `amount = close × volume` (Sina volume 字段单位是"股", 不是手)
- **AND** `turnover` 字段在 Sina 兜底时填 0 (Sina K-line 不返回换手率), 由后续 `enrich_with_tencent_snapshot` 二次回填
- **AND** `source` 标记为 `"sina-amount-estimated"` 便于审计区分估算值

#### Scenario: 腾讯快照二次回填 turnover

- **WHEN** backtest_data 表中某行 `turnover = 0` 或 `amount = 0` (Sina 估算标记)
- **THEN** `enrich_with_tencent_snapshot(codes)` **MUST** 通过 `https://qt.gtimg.cn/q={sina_code}` 拉取当日快照
- **AND** **MUST** 回填 `turnover` (parts[38], 百分比数值) 与校验 `amount` (parts[37], 万元 → 元)
- **AND** 接口限流 50 只/批, 单次调用间隔 0.5s
- **AND** 拉取失败的 code 跳过, 不抛异常

### Requirement: batch_prefetch_all 非交易时段判断

`batch_prefetch_all.py` 的 `is_trading_time` 判断 **MUST** 覆盖 A 股盘后时段(15:00-15:30), 此时 akshare 仍可拉当日完整数据, 不应走 Sina fallback.

#### Scenario: 盘后 15:00-15:30 仍走 akshare

- **WHEN** 当前时间为工作日 15:00 ≤ hour ≤ 15 (含 15)
- **THEN** `is_trading_time` **MUST** 为 `True`
- **AND** **MUST** 优先尝试 akshare 拉取当日数据(含 amount/turnover)
- **AND** akshare 失败后才回退到 Sina

#### Scenario: 周末/节假日 走 Sina

- **WHEN** 当前时间为周末或法定节假日
- **THEN** `is_trading_time` **MUST** 为 `False`
- **AND** **MUST** 跳过 akshare, 直接走 Sina 兜底(amount 由 close×volume 推算)
