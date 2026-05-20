# 模拟盘系统实现计划

> 按照设计文档 paper-trading-design.md 实现

---

## Task 1: 数据库模型 — 新增5张表

**文件：** `models.py`
**操作：** 新增 PaperAccount, PaperPosition, PaperOrder, PaperSnapshot, EtfReplacementMap

**迁移：** 重启后端自动重建表（SQLite + Base.metadata.create_all）

## Task 2: 核心交易逻辑 paper_trading.py

**新建：** `paper_trading.py`
**内容：**
- `create_order(account_id, code, name, direction, price, quantity, order_type, note)` — 下单核心函数
  - 买入：扣减 cash_balance，更新/新建持仓
  - 卖出：增加 cash_balance，减少/删除持仓
  - 自动计算佣金（万2.5，最低5元）、印花税（卖出万10）
  - ETF自动替换检测
  - 更新账户 total_market_value, total_profit_pct
- `calculate_account_stats(account_id)` — 重算收益率、最大回撤、胜率
- `create_snapshot(account_id)` — 创建快照，记录当前总资产
- `calculate_win_rate(account_id)` — 胜率计算

## Task 3: 后端CRUD API — 账户、持仓、订单、快照

**文件：** `db.py`（新增CRUD函数）+ `api_routes.py`（新增路由）

**CRUD函数：**
- `get_paper_accounts()`, `create_paper_account()`, `update_paper_account()`, `delete_paper_account()`
- `get_paper_positions(account_id)`
- `get_paper_orders(account_id, page, per_page)`
- `get_paper_snapshots(account_id, limit)`
- `get_equity_curve(account_id)` — 格式化收益曲线数据

**API路由：**
- `GET/POST /api/paper/accounts`
- `PUT/DELETE /api/paper/accounts/:id`
- `POST /api/paper/accounts/:id/orders` — 下单
- `GET /api/paper/accounts/:id/positions`
- `GET /api/paper/accounts/:id/orders`
- `POST /api/paper/accounts/:id/snapshot` — 手动触发快照
- `GET /api/paper/accounts/:id/equity_curve`

## Task 4: ETF映射API + 自动替换逻辑

**文件：** `paper_trading.py` + `api_routes.py`

**内容：**
- 内置科创板→ETF默认映射表（可在 EtfReplacementMap 中配置）
- `resolve_etf_replacement(code)` — 查询映射表，返回替代ETF信息
- ETF映射CRUD路由
- 下单时自动替换逻辑集成到 `create_order`

**默认映射：**
| 条件 | 替代ETF |
| 推荐任意688xxx | 588000（科创50ETF） |
| 推荐3只以上688xxx | 588080（科创100ETF） |

## Task 5: 策略联动 — 信号应用到模拟盘

**文件：** `api_routes.py`

**POST /api/strategy/run/:strategy_id/apply_to_paper**
- Body: `{account_id, signals: [{code, name, direction, price, quantity}]}`
- 批量下单
- 记录 strategy_run_id

## Task 6: 前端模拟盘总览页 `/paper`

**新建：** `stock_frontend/src/pages/PaperAccounts.tsx`
**内容：**
- 账户卡片网格
- 每个卡片显示：名称、总资产、收益率、回撤、胜率、持仓数
- 创建新账户按钮 + 弹窗
- 编辑/删除
- 点击进入详情

## Task 7: 前端账户详情页 `/paper/:id`

**新建：** `stock_frontend/src/pages/PaperDetail.tsx`
**内容：**
- 顶部：账户概况（总资产、现金、市值、收益率、回撤）
- 收益曲线图（使用 lightweight-charts 折线图）
- 快照间隔设置
- 手动交易按钮 → TradeModal
- 持仓表格
- 订单历史表格（可折叠分页）

## Task 8: 手动交易弹窗 TradeModal

**新建：** `stock_frontend/src/components/TradeModal.tsx`
**内容：**
- 搜索/输入股票代码
- 自动填写当前市价
- 方向选择（买入/卖出）
- 数量输入
- 备注（可选）
- 二次确认

## Task 9: 策略信号应用面板 ApplyToPaperPanel

**新建：** `stock_frontend/src/components/ApplyToPaperPanel.tsx`
**集成到：** `stock_frontend/src/pages/StrategyRun.tsx`
**内容：**
- 在策略运行结果页底部
- 选择模拟盘账户下拉
- 自动解析策略信号列表
- 确认执行

## Task 10: 路由注册 + 侧边栏导航

**文件：** `App.tsx`, `Layout.tsx`
**修改：**
- App.tsx: 新增 `/paper`, `/paper/:id` 路由
- Layout.tsx: 侧边栏增加「模拟盘」导航项
