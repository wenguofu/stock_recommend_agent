# 模拟盘系统设计方案

> 用于跟踪验证量化策略的有效性

## 一、数据模型

### 1.1 PaperAccount（模拟盘账户）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 自增ID |
| name | String(100) | 账户名称（如"游资策略盘"） |
| strategy_id | Integer FK | 关联的策略ID（可为空，手动盘） |
| initial_capital | Float | 初始资金 |
| cash_balance | Float | 可用余额 |
| total_market_value | Float | 持仓总市值 |
| total_profit_pct | Float | 总收益率 |
| max_drawdown | Float | 最大回撤率 |
| win_rate | Float | 胜率（盈利交易/总交易） |
| snapshot_interval | Integer | 快照间隔（分钟，默认60） |
| include_etf_replacement | Boolean | 是否自动替换科创板到ETF（默认True） |
| enabled | Boolean | 是否启用 |
| created_at | DateTime | |

### 1.2 PaperPosition（模拟盘持仓）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | |
| account_id | Integer FK | 关联账户 |
| code | String(6) | 股票代码 |
| name | String(50) | 股票名称 |
| shares | Integer | 持仓股数 |
| avg_cost | Float | 平均成本价 |
| current_price | Float | 当前价 |
| market_value | Float | 持仓市值 |
| profit_pct | Float | 总盈亏比例 |
| today_profit_pct | Float | 当日盈亏比例 |
| etf_replaced | Boolean | 是否已替换为ETF |
| original_code | String(6) | 原始推荐的股票代码（ETF替换时记录） |
| updated_at | DateTime | |

### 1.3 PaperOrder（交易记录）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | |
| account_id | Integer FK | |
| code | String(6) | |
| name | String(50) | |
| direction | String(4) | buy / sell |
| price | Float | 成交价格 |
| quantity | Integer | 成交数量 |
| amount | Float | 成交金额 |
| commission | Float | 佣金（默认万2.5） |
| tax | Float | 印花税（卖出的万10） |
| order_type | String(10) | manual / signal / auto |
| strategy_run_id | String(64) | 关联的策略运行ID（signal类型时） |
| note | Text | 备注 |
| created_at | DateTime | |

### 1.4 PaperSnapshot（每日/定时快照 → 收益曲线）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | |
| account_id | Integer FK | |
| snapshot_time | DateTime | 快照时间 |
| total_value | Float | 总资产（现金+市值） |
| cash_balance | Float | |
| market_value | Float | |
| daily_pnl | Float | 当日盈亏额 |
| daily_pnl_pct | Float | 当日盈亏比例 |

### 1.5 EtfReplacementMap（ETF替代映射表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | |
| original_code | String(6) | 原始科创板代码 |
| original_name | String(50) | |
| etf_code | String(6) | 替代ETF代码 |
| etf_name | String(50) | |
| ratio | Float | 替代比例（ETF价格/股数换算） |
| created_at | DateTime | |

## 二、后端API

### 账户管理
- `GET /api/paper/accounts` — 列表
- `POST /api/paper/accounts` — 创建（含初始资金）
- `PUT /api/paper/accounts/:id` — 更新（名称、快照间隔等）
- `DELETE /api/paper/accounts/:id` — 删除（需确认）
- `POST /api/paper/accounts/:id/calculate` — 手动触发重新计算盈亏/回撤

### 交易操作
- `POST /api/paper/accounts/:id/orders` — 下单（buy/sell）
- `GET /api/paper/accounts/:id/orders` — 订单历史（分页）
- `GET /api/paper/accounts/:id/positions` — 当前持仓

### 快照/曲线
- `GET /api/paper/accounts/:id/snapshots` — 快照列表（分页）
- `GET /api/paper/accounts/:id/equity_curve` — 收益曲线数据（前端画图）

### ETF映射
- `GET /api/paper/etf-map` — ETF映射列表
- `POST /api/paper/etf-map` — 手动添加映射
- `DELETE /api/paper/etf-map/:id` — 删除映射
- `GET /api/paper/etf-map/search?code=688xxx` — 搜索ETF替代（调AKShare或内置）

### 策略联动
- `POST /api/strategy/run/:id/apply_to_paper` — 策略运行结果应用到模拟盘
  - Body: `{account_id, signals: [{code, direction, price, quantity}]}`

## 三、前端页面

### 3.1 模拟盘总览页 `/paper`

**功能：**
- 顶部：创建新模拟盘按钮 + 搜索/筛选
- 账户卡片网格，每张卡片显示：
  - 账户名称 + 绑定策略名（如有）
  - 总资产 / 总收益率（带颜色，红涨绿跌）
  - 最大回撤 / 胜率
  - 持仓数
  - 「进入账户」按钮
  - 编辑/删除按钮

### 3.2 账户详情页 `/paper/:id`

**布局（左-右两栏）：**

**左栏：账户概况**
- 总资产、现金、市值、收益率、回撤
- 简易收益曲线图（使用 lightweight-charts 或简单 SVG）
- 快照间隔设置
- 手动交易入口按钮

**右栏：持仓列表（表格）**
- 代码 / 名称 / 持仓股数 / 均价 / 现价 / 市值 / 盈亏%
- ETF替换标识（标签显示）

**下方：订单历史**
- 可折叠表格：时间 / 方向 / 代码 / 价格 / 数量 / 金额 / 类型 / 备注

### 3.3 手动交易弹窗

**模态框内容：**
- 搜索/输入股票代码 + 名称自动填充
- 方向：买入 / 卖出（单选）
- 价格：自动填充当前市价，可手动修改
- 数量：输入
- 备注（可选）
- 确认按钮 + 二次确认弹窗

### 3.4 策略信号应用（在策略运行页底部）

策略运行完成后，结果区域新增按钮：
- 「应用信号到模拟盘」
- 下拉选择已有模拟盘账户
- 自动解析报告中推荐买入/卖出的股票
- 展示信号预览列表（代码、方向、建议价格、建议数量）
- 「确认执行」触发批量下单

## 四、核心技术逻辑

### 4.1 下单逻辑

```
buy:  cash_balance -= amount + commission
      position.shares += quantity
      position.avg_cost = (cost_before + amount) / total_shares

sell: cash_balance += amount - commission - tax
      position.shares -= quantity
      if position.shares == 0: delete position
```

手续费规则（内置，后续可配置）：
- 佣金：成交额 × 0.025%（万2.5），最低5元
- 印花税：卖出时成交额 × 0.1%（万10）
- 过户费：成交额 × 0.001%（万0.1）

### 4.2 ETF自动替换

下单时检测：
1. 股票代码是否以 `688` 开头（科创板）或为美股
2. 是否是已配置的 `EtfReplacementMap` 中的代码
3. 若匹配 → 自动替换为ETF，记录 original_code
4. 计算替代比例：根据ETF和原始股的价格比率换算股数
5. 在订单/持仓备注中标记「[ETF替代] 原推荐: 688xxx」

### 4.3 定时快照

通过盯盘任务系统（已有 MonitorTask）：
- 每个开启了自动快照的模拟盘，注册一个 MonitorTask
- 任务执行时调用 `POST /api/paper/accounts/:id/snapshot`
- 快照内容：当前现金 + 持仓市值（调用实时行情刷新current_price）
- 间隔 = 该账户的 `snapshot_interval`

### 4.4 收益曲线渲染

前端使用 lightweight-charts（已在项目中），在账户详情页画折线图：
- X轴：快照时间
- Y轴：total_value
- 叠加基准线（沪深300 or 科创50，可选）

## 五、项目文件变更清单

### 后端（根目录）
| 文件 | 操作 | 说明 |
|------|------|------|
| `models.py` | 修改 | 新增 PaperAccount, PaperPosition, PaperOrder, PaperSnapshot, EtfReplacementMap |
| `db.py` | 修改 | 新增各模型CRUD操作 |
| `api_routes.py` | 修改 | 新增 /api/paper/* 和 /api/strategy/run/:id/apply_to_paper |
| 新建 `paper_trading.py` | 新建 | 核心交易逻辑（下单、清算、盈亏计算、快照） |

### 前端（stock_frontend/）
| 文件 | 操作 | 说明 |
|------|------|------|
| `src/services/api.ts` | 修改 | 新增模拟盘API调用 |
| `src/pages/PaperAccounts.tsx` | 新建 | 模拟盘总览页 |
| `src/pages/PaperDetail.tsx` | 新建 | 账户详情页（持仓+订单+曲线） |
| `src/components/TradeModal.tsx` | 新建 | 手动交易弹窗 |
| `src/components/ApplyToPaperPanel.tsx` | 新建 | 策略信号应用面板 |
| `src/App.tsx` | 修改 | 新增路由 /paper, /paper/:id |
| `src/components/Layout.tsx` | 修改 | 侧边栏增加模拟盘入口 |

## 六、ETF映射自动搜索Skill

新建 Skill `etf-mapper`，路径 `~/.hermes/skills/finance/etf-mapper/SKILL.md`

**功能：** 给定一个科创板股票代码（如688xxx），自动：
1. 查询该股票所属行业/概念
2. 搜索对应A股ETF（如科创50、科创100、半导体ETF等）
3. 推荐最匹配的ETF + 替代比率
4. 支持批量搜索

## 七、实施步骤

```
Task 1: 数据库模型 + 建表迁移
Task 2: 后端核心交易逻辑 paper_trading.py
Task 3: 后端CRUD API（账户、持仓、订单）
Task 4: 后端ETF映射API + 自动替换逻辑
Task 5: 后端快照机制（定时+手动触发）
Task 6: 后端策略联动接口（信号应用到模拟盘）
Task 7: 前端模拟盘总览页 /paper
Task 8: 前端账户详情页 /paper/:id（持仓+订单+曲线）
Task 9: 前端手动交易弹窗 TradeModal
Task 10: 前端策略信号应用面板 ApplyToPaperPanel
Task 11: 侧边栏导航 + 路由注册
Task 12: ETF映射自动搜索 Skill
```

---

**请审阅这份设计文档，确认后我写实现计划开始编码。**
