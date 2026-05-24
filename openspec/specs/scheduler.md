# Scheduler — 内置任务调度器

## 架构

`TaskScheduler` 类，在 `api_server.py` 启动时以 daemon 线程运行。

## 任务清单 (8个)

| 任务 | 类型 | 调度 | 条件 |
|------|------|------|------|
| 盯盘提醒 | interval | 300s | 交易时段 |
| 斯达监控 | interval | 1800s | 交易时段 |
| 板块更新 | cron | `0 9 * * 1-5` | 日期去重 |
| 自动交易 | cron | `0 9,11,13,15 * * 1-5` | 小时去重 |
| 全A股刷新 | cron | `0 10 * * 1-5` | 日期去重 |
| 板块分析 | cron | `30 15 * * 1-5` | 收盘后 |
| 推荐生成 | cron | `0 16 * * 1-5` | 收盘后 |
| 自选股刷新 | cron | `*/30 9-15 * * 1-5` | — |

## 补跑机制

`_catchup_missed_cron()`：服务重启后检查当天是否错过 cron 时间点，补跑一次。范围/步进表达式（如 `9-15`, `*/30`）自动跳过补跑。

## 日志

- `logs/scheduler.log` — 运行日志
- `logs/scheduler_outputs.json` — 最近 200 条输出

## 监控 API

```
GET /api/scheduler/status  → 任务状态列表
GET /api/scheduler/logs?limit=20  → 最近输出
```

## 已知问题

- [ ] cron 去重逻辑有两种方式 (`last_date` vs `_last_hour`)，不一致
- [ ] `task_check_stada` 硬编码 603290 代码，不是通用监控
- [ ] 无任务依赖关系（如必须先刷新数据再生成推荐）
