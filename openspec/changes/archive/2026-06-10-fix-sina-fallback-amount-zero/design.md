# Design — Sina Fallback amount/turnover 修复

## 现状

```python
# batch_prefetch_all.py
def _sina_to_records(data, days):
    ...
    records.append({
        ...
        "amount": 0,         # ← bug: 硬编码
        "turnover": 0,       # ← bug: 硬编码
        "source": "sina",
    })
```

## 修复方案

### 1. `_sina_to_records` 推算 amount

Sina K-line 接口返回字段是 `{day, open, high, low, close, volume}`。
Sina 行情接口的 `volume` 字段单位是**股**（不是手），参见实际数据验证：
- 002222 close=88.03, vol=20434089 → 实盘成交 17.98 亿 ✓（vol=股时 amount = 88.03 × 20434089 = 17.99 亿）
- 002407 close=34.72, vol=155157709 → 实盘成交 ~53.9 亿 ✓

```python
# 推算
amount = close * volume          # 元
turnover = 0                     # Sina K-line 无换手率, 留 0 标记待补
source = "sina-amount-estimated"
```

### 2. `fetch_stock_data` 非交易时段判断加盘后 15:00-15:30

A 股盘后（15:00-15:30）东方财富接口仍可拉当日数据，akshare 也能跑通；应让非交易时段判断更准确：

```python
is_trading_time = (
    now.weekday() < 5 and (
        (now.hour == 9 and now.minute >= 30) or
        10 <= now.hour <= 11 or
        13 <= now.hour <= 15   # 改成 15 (含盘后)
    )
)
```

### 3. 新增 `enrich_with_tencent_snapshot(codes)`

批量拉完后调用一次：把 amount=0 或 turnover=0 的行（code + 最新日期）喂给 `qt.gtimg.cn`，补 turnover + 校验 amount。

```python
def enrich_with_tencent_snapshot(codes: List[str]) -> int:
    """回填 amount/turnover 字段（Sina 兜底后用腾讯快照校验）"""
    updated = 0
    for code in codes:
        snap = _fetch_tencent_snapshot(code)  # 调 qt.gtimg.cn
        if not snap: continue
        # UPDATE backtest_data SET amount=?, turnover=? WHERE code=? AND date=MAX(date)
        updated += 1
    return updated
```

### 4. 数据契约 spec

`openspec/specs/market-data.md` L10：

```
| `get_daily_kline(code, count)` | backtest_data 表 → Sina 兜底 | [{day,open,high,low,close,volume,amount,turnover}] |
```

注脚：

> Sina 兜底 amount = close × volume (volume 单位为"股")；turnover 由腾讯快照 (qt.gtimg.cn) 二次回填。

## 不改的部分

- `save_backtest_data_batch` (db.py): 已经能存 amount/turnover，无需改
- `BacktestData` 模型: 字段已存在
- `_df_to_records` (akshare 路径): 已有 amount/turnover

## 风险

1. 腾讯快照接口限流 50 只/批（spec 已有约束）→ enrich 函数自己加 0.5s 间隔
2. amount = close × volume 在停牌/集合竞价场景下可能不准 → 保留 source="sina-estimated" 标记，便于审计
3. zisuye 的 `_estimate_market_cap_yi` 用 amount/turnover 算市值，turnover 仍走估算（无变化）
