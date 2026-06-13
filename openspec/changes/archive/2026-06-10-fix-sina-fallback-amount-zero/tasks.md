# Tasks — Fix Sina Fallback amount/turnover 修复

## 1. TDD Red — 写复现测试 (test_batch_prefetch_sina.py)
- [x] 1.1 测试 `_sina_to_records` 当前行为: amount=0 (复现 bug)
- [x] 1.2 测试修复后期望: amount = close × volume
- [x] 1.3 测试 `enrich_with_tencent_snapshot` 行为: mock 腾讯接口
- [x] 1.4 测试 `fetch_stock_data` 盘后 15:00-15:30 仍走 akshare 分支

## 2. TDD Green — 修 batch_prefetch_all.py
- [x] 2.1 `_sina_to_records` 计算 amount = close × volume, source='sina-amount-estimated'
- [x] 2.2 `fetch_stock_data` is_trading_time 上界改成 15 (含盘后)
- [x] 2.3 新增 `_fetch_tencent_snapshot(code)` 私有函数
- [x] 2.4 新增 `enrich_with_tencent_snapshot(codes)` 公用函数
- [x] 2.5 `batch_run` 末尾调 `enrich_with_tencent_snapshot(pending_codes)`

## 3. Spec 同步 — openspec/specs/market-data.md
- [x] 3.1 L10 get_daily_kline 返回结构加 amount, turnover (via delta in specs/market-data/spec.md)
- [x] 3.2 加注脚说明 Sina amount 是 close × volume 推算, turnover 走腾讯快照二次回填 (via delta Scenario)
- 注: openspec/specs/market-data.md 单文件格式不被 archive 系统识别 (pre-existing infra issue, see market-trend-monitor 同类问题); 走 --skip-specs 归档

## 4. 验证
- [x] 4.1 `pytest -q tests/test_batch_prefetch_sina.py` 全绿 (11/11)
- [x] 4.2 全量 `pytest tests/` 192 passed / 1 pre-existing torch e2e 失败 / 11 新增, 整体不挂
- [x] 4.3 `openspec validate --strict` 通过
- [x] 4.4 重跑 zisuye 2026-06-10 验证 amount/turnover 字段有值 (绿色)
