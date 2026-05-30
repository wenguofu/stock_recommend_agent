# Paper Trading — 模拟盘系统

## 架构

```
paper_trading.py (749行, 13函数)
paper_accounts / paper_positions / paper_orders / paper_snapshots / paper_plans / paper_auto_rules
```

## 核心规则

### 实盘价格验证
所有交易通过 Sina API 验证，下单价与实盘偏差 >10% 自动拒绝。

### 费用模拟
- 买入: 佣金万2.5 (最低5元)
- 卖出: 佣金万2.5 + 印花税千1

### ETF替代
科创板 (688xxx) 自动替换为 588000 (科创50ETF)，标记 `etf_replaced=true`。

## 买卖计划 (PaperPlan)

从策略推荐一键生成 3 条计划：买入 + 止盈(+15%) + 止损(-7%)

## API

| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/paper/accounts` | GET/POST | 账户列表/创建 |
| `/api/paper/accounts/<id>` | GET/PUT/DELETE | 账户详情/更新/删除 |
| `/api/paper/accounts/<id>/orders` | GET/POST | 订单查询/创建 |
| `/api/paper/accounts/<id>/positions` | GET | 持仓查询 |
| `/api/paper/accounts/<id>/snapshot` | POST | 手动快照 |
| `/api/paper/accounts/<id>/summary` | GET | 账户摘要 |
| `/api/paper/accounts/<id>/equity_curve` | GET | 净值曲线 |
| `/api/paper/plans/<account_id>` | GET/POST | 买卖计划 |
| `/api/paper/profit-ranking` | GET | 收益排名 |
| `/api/paper/profit-breakdown` | GET | 收益分解 |

## 已知问题

- [ ] 不支持空头/融券
- [ ] 快照定时器硬编码 60分钟默认
- [ ] 无交易滑点模拟

## Risk Control Integration (2026-05-30)

Every `create_order()` call now runs through `risk_control.hard_constraints.validate_order()` before execution. If any of 7 hard constraints are violated, the order is blocked with a structured error response containing `violations[]` and `warnings[]`.
