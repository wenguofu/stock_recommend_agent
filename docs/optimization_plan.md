# A-Stock Trading 深度审查与优化计划

> 审查日期: 2026-06-06 | 范围: 全部后端(80+ 模块) + 前端(22 页面) + ML/策略
> 方法: 逐文件代码审计 + 静态依赖分析 + 关键路径追踪
> 参考: novel-agent 的"5 阶段 Sprint 路线图"方法论(止血 → 对齐 → 加固 → 扩展 → 高级)

---

## 0. 执行摘要 (TL;DR)

| 维度 | 现状 | 主要风险 |
|------|------|----------|
| **代码体量** | 后端 ~100 个 .py 文件,前端 ~11k 行 TS/TSX | 8 个巨型文件 (>30KB),`api_routes.py` 148KB 极危 |
| **静默吞错** | 18+ 处 `except: pass`,其中 4 处零日志 | 资金路径(PaperOrder)、数据落库(DB 写入)可无声失败 |
| **测试覆盖** | 22 个前端 + 18 个后端测试,**核心 0 覆盖** | `api_routes`/`data_fetchers`/`paper_trading`/`db`/`ml_predictor` 全部裸奔 |
| **模型治理** | 3 个 .pt 硬编码加载,无版本/无 hash/无训练日期 | 任何重训会静默覆盖生产权重,且无 A/B / 漂移监控 |
| **资金安全** | 风险控制 `except` 兜底放行 + 无订单去重 + 无行锁 | 任一 HardConstraint 异常 → 全部订单绕过风控 |
| **响应一致性** | `error_handler` 定义了 `api_success/api_error`,但 266 处端点直接 `jsonify` | 前端解析逻辑需写 N 套,错误处理散落 |
| **可观测性** | `/api/health` 只返 `status: ok`,无 DB/外部 API/调度器深检 | 线上出问题全靠 grep log |

**最紧急的 3 件事** (建议 24h 内处理):
1. **修复 `api_routes.py` 重复 except 块** → 模块无法 import,`/api/strategy/batch_backtest` 死路径
2. **改 `paper_trading` 风控 fail-closed 模式** → 任何导入/运行异常不再静默放行
3. **加 `ml_predictor.load()` 版本校验** → 避免特征维度不匹配时静默错位

---

## 1. 发现的缺陷 (按严重度)

### 🔴 P0 — 阻断性 Bug / 资金安全

#### 后端核心

| ID | 位置 | 描述 |
|----|------|------|
| **BUG-01** | [api_routes.py:3017-3024](api_routes.py#L3017) | `strategy_batch_backtest()` 含两个连续 `except Exception`,Python 抛 `SyntaxError`,模块 import 失败,相关端点全挂 |
| **BUG-02** | [data_fetchers.py:519](data_fetchers.py#L519) | `db2.execute(db2.text(...))` 中 `db2` 是 `Session` 不是 `Engine`,SQLAlchemy 1.4+ 立即 `AttributeError`;路径被 `except: pass` 静默吞掉 |
| **BUG-03** | [data_fetchers.py:1031-1048](data_fetchers.py#L1031) | `get_latest_financial` 用回测缓存最后一行算 PE,交易时段返回过期 PE,影响估值/AI 提示 |
| **BUG-04** | [api_routes.py:2962-2969](api_routes.py#L2962) | `signal_fuse` 在循环中重复 `db = next(get_db())` 不关闭,batch 10+ 触发连接池耗尽 → 5xx |
| **BUG-05** | [scheduler.py:551-569](scheduler.py#L551) | `_run_task` 无锁,可被 HTTP `/api/scheduler/trigger` 手动并发触发 → 多线程写同一 db session 撞 `Session is closed` |
| **BUG-06** | [api_routes.py:2772-2824](api_routes.py#L2772) | `/api/backtest/run`、`/api/forecast` 在 HTTP 线程同步跑 30s+ 长任务,无 timeout,卡 Gunicorn worker |
| **BUG-07** | [data_fetchers.py:1498-1566](data_fetchers.py#L1498) | `get_industry_comparison` 备用方法顺序遍历 25 行业×8s 超时,最坏 200s+,无并发 |
| **BUG-08** | [data_fetchers.py:296-300](data_fetchers.py#L296) | 美股解析失败 `return None` 不打 trace,定位只能看 "无法获取实时行情数据" |
| **BUG-09** | [api_routes.py:2699-2720](api_routes.py#L2699) | `/api/screening/layer*` 无 body 大小限制,且为同步长任务 |
| **BUG-10** | [paper_trading.py:237-240](paper_trading.py#L237) | **资金安全 P0**:风控 `except` 兜底放行,任何异常让所有订单绕过风控 |
| **BUG-11** | [api_routes.py:3102-3155](api_routes.py#L3102) | `subprocess.run(uv ...)` 沙箱缺失,可被同机其他用户/前端参数触发执行任意脚本 |

#### 前端

| ID | 位置 | 描述 |
|----|------|------|
| **BUG-UX-01** | `Strategy.tsx:134,206` / `StrategyRecommend.tsx` | 关键操作反馈用 `alert()` 阻塞主线程,与 antd `message` 体系不一致 |
| **BUG-UX-03** | `StockDetail.tsx:23-145` | 单页面 9 个 `useQuery` 并发拉取,慢网触发接口雪崩 |
| **BUG-UX-04** | `Strategy.tsx:206` | paper plan 提交后不 `invalidateQueries(['paper-plans'])` |
| **BUG-UX-05** | 7+ 文件 | 关键操作失败只 `console.error`,用户无感知 (`Watchlist`/`Strategy`/`AIDebate`/`Settings`/`StockDebate`/`Midline` 等) |
| **BUG-UX-07** | `Watchlist.tsx:82-88` | 加载失败无 UI 兜底,误显示"暂无自选股" |
| **BUG-UX-08** | `BacktestPage.tsx:140-144` | `DatePicker` `value={startDate ? undefined : undefined}` 永远 undefined,日期回测无法选择 |
| **BUG-UX-09** | `StockDetail.tsx:115-117` | `window.__positionData` 全局污染 |
| **BUG-UX-10** | `AIAnalyzeButton.tsx:22-34` | modal 关闭未重置 `selectedAgentIds`,下次打开残留选择 |

#### ML / 资金

| ID | 位置 | 描述 |
|----|------|------|
| **BUG-ML-01** | [ml_predictor.py:58-63](ml_predictor.py#L58) | DL 模型无版本管理,`short_term_latest.pt` 硬编码,任何重训静默覆盖 |
| **BUG-ML-02** | [ml_predictor.py:79-103](ml_predictor.py#L79) | `_daily_to_weekly()` 把 20 维日线 cat 给 8 价+6 基的 `MidTermPredictor`,**维度对不上** |
| **BUG-ML-03** | [factor_engine.py:441](factor_engine.py#L441) | `debt_ratio` 用启发式 `gross_margin/ROE*5` 反推,不是真实资产负债率 |
| **BUG-ML-04** | [strategy_backtest.py:296-319](strategy_backtest.py#L296) | 回测用"今日 PE"代替历史 PE,**系统性高估基本面策略胜率** |
| **BUG-ML-06** | `strategies/breakout.py:68-71` 等 3 处 | 三处 RSI 实现各异,不等同 Wilder 滚动 |
| **BUG-ML-07** | `screening/layer1_tech_screen.py:67-73` | `is_market_safe_for_screening()` 失败 fallback 返 `True`,网络异常放行筛选 |
| **BUG-ML-09** | [paper_trading.py:126-394](paper_trading.py#L126) | `create_order` 无订单去重、无行锁,`position.shares -= quantity` 可超卖 |
| **BUG-ML-10** | [seed_strategies.py:1-9](seed_strategies.py#L1) | DEPRECATED 但仍可调,DB 落库 `agent_configs` 不被 `score_by_strategy` 引用,**两套体系并存不对账** |

---

### 🟡 P1 — 架构/设计缺陷

#### 后端架构

| ID | 描述 | 位置 |
|----|------|------|
| **ARCH-01** | `api_routes.py` 148KB / 3208 行,涵盖 30+ 业务域,自带注释"需逐步拆分" | api_routes.py |
| **ARCH-02** | 缺乏统一响应格式:266 处 `jsonify`,key 命名混用 10+ 种 | 全后端 |
| **ARCH-03** | 双轨/三轨数据获取:`data_fetchers` 直连 vs `db.get_backtest_data` 缓存 vs 调度器 prefetch | data_fetchers.py / scheduler.py |
| **ARCH-04** | 配置硬编码:佣金/印花税/批量限额/大盘阈值散落代码 | paper_trading.py / api_routes.py |
| **ARCH-05** | 缓存策略缺失/重复:closure 缓存无并发保护,无 Redis,横向扩容无效 | paper_trading / market_outlook |
| **ARCH-06** | 缺乏可观测性:`/api/health` 只返 ok,无 `/metrics` 端点,无 LLM token 追踪 | api_routes.py:116 |
| **ARCH-07** | `rate_limiter` 已定义但**装饰器从未挂载**,LLM 端点可被暴力刷 | rate_limiter.py + 全后端 |
| **ARCH-08** | CORS 过宽 (`CORS(app)` 无白名单) | api_server.py:25 |
| **ARCH-09** | `ai_service.call_agent` 重试只覆盖 ReadTimeout/ConnectionError,HTTP 5xx/429 不重试 | ai_service.py:99-110 |
| **ARCH-10** | `scheduler_outputs.json` 多线程写无锁 | scheduler.py:470-487 |
| **ARCH-11** | ORM `String(10)` 存日期,无法索引 `BETWEEN` | models.py:410 |
| **ARCH-12** | `__pycache__`、`.env`、`database.db-wal`、`.pt` checkpoint 入库 | .gitignore |

#### 前端架构

| ID | 描述 |
|----|------|
| **ARCH-UX-01** | 8 个巨型页面 (>500 行):`PaperDetail.tsx:779` / `StockDetail.tsx:675` / `Home.tsx:609` 等 |
| **ARCH-UX-02** | 18 个文件、50+ 处绕过 `stockAPI` 直接 `fetch()` |
| **ARCH-UX-03** | 业务逻辑混入视图:StockDebate/SectorPrediction 解析 60+ 行,StrategyLibrary `renderDoc` |
| **ARCH-UX-04** | 重复组件:`formatMoney` 5 份,`isTradingTime` 2 份,inline `Watchlist*Cell` 3 份 |
| **ARCH-UX-05** | 状态管理:仅 2 个 zustand store,12+ 实体散落组件 state |
| **ARCH-UX-06** | `ErrorBoundary` 包整个 Routes,单页崩溃全站白屏 |
| **ARCH-UX-07** | 9+ 并行 query 无 skeleton,只有 `isLoading` flash |
| **ARCH-UX-08** | `PaperDetail.tsx:236-275` 内嵌 40+ 行 chart 逻辑 |

#### ML 架构

| ID | 描述 |
|----|------|
| **ARCH-ML-01** | DL 模型 `key_drivers` 硬编码 `[]`,无 SHAP/Attention rollout |
| **ARCH-ML-02** | 缺模型性能监控:无 PSI/KS、特征分布、ECE、IC 滚动 |
| **ARCH-ML-03** | 缺 A/B / 影子模式:`_dl_models_cache` 单例,新模型只能覆盖 |
| **ARCH-ML-04** | 模型再训练流程不闭环:无 PyTorch 训练器,`tune_rf_*.py` 是 RF 调参 |
| **ARCH-ML-05** | 特征缓存缺失:`get_feature_vector` 每次现算,`watchlist-health` 跑 N 个 RF 现训 |
| **ARCH-ML-06** | `factor_engine.debt_ratio` 不可解释 |
| **ARCH-ML-07** | `MidTermPredictor` 21.7 MB checkpoint 实际**未被任何 API 调用** |
| **ARCH-ML-08** | `onnx_export.export_all()` 无调用方,ONNX Runtime 未接入 |
| **ARCH-ML-09** | `_dl_models_cache` 全局单例 + `weights_only=False` 反序列化风险 |
| **ARCH-ML-10** | `calibration.py` 定义完整但全仓 0 引用,概率未校准 |
| **ARCH-ML-11** | `factor_attribution.calc_ic_series` 启发式 `ic_std = abs(ic)*0.5`,IR/t_stat 全是假指标 |

---

### 🟢 P2 — 体验/可维护性 (节选)

| ID | 描述 |
|----|------|
| **FEAT-01** | 静默 print 滥用:`api_routes.py` 74 处 `print`,0 logger;`data_fetchers.py` 354 处 print |
| **FEAT-02** | 错误处理不分类:80+ 处 `except` 全部返 500,`AppError` 子类未使用 |
| **FEAT-03** | 类型注解缺失:`data_fetchers`/`api_routes` 几乎全无 |
| **FEAT-04** | 测试覆盖严重不足:`api_routes`/`data_fetchers`/`paper_trading`/`db`/`ml_predictor` 全部 0 测试 |
| **FEAT-07** | `get_sina_daily` 字段漂移: `r.get('date', '')` vs `r.get('day', '')` |
| **FEAT-08** | `/api/sector-prediction` 读文件系统无 path 校验,`date_param=../` 可越权读 |
| **FEAT-10** | `rate_limiter` `_requests` dict 永增长,生产 24h 后 10k+ key |

#### 前端体验

| ID | 描述 |
|----|------|
| **FEAT-UX-01** | 涨跌颜色不一致:15+ 文件正确(红涨/绿跌),5+ 文件反向(同屏混用) |
| **FEAT-UX-02** | 字号硬编码 60+ 处,`theme.ts` 无 size token |
| **FEAT-UX-03** | 缺移动端响应式,`Col xs={24} lg={6}` 在 <768px 仍 3 列 |
| **FEAT-UX-04** | 缺键盘快捷键,`?` 帮助/`/` 搜索自选/`g h` 跳首页 |
| **FEAT-UX-05** | 测试 22 个,集成测试 0,`package.json` 无 `test` 脚本 |
| **FEAT-UX-09** | `theme.ts` 定义 dark 但 `App.tsx:40-46` 硬编码 light,无切换 UI |

#### ML 体验

| ID | 描述 |
|----|------|
| **FEAT-ML-01** | 策略配置 UI 缺失,`STRATEGIES` 阈值硬编码 |
| **FEAT-ML-02** | 回测结果可视化弱,无 equity curve / 信号点 / 收益分布图 |
| **FEAT-ML-04** | 缺"信号→订单"链路追溯,`PaperOrder.strategy_run_id` 字段未被填 |
| **FEAT-ML-07** | 热门板块成分股硬编码,`hot_sector_manager` 永远空,实际回退全市场 |
| **FEAT-ML-08** | 缺"模型今日预测 vs 实际"日对比面板,`predict_with_dl` 无落库 |

---

## 2. 统计指标

| 指标 | 数量 |
|------|------|
| 静默 `except: pass` / `except Exception: pass` | **18 处** (其中 4 处零日志) |
| 真正零日志/无通知的吞错 | **4 处** (data_fetchers.py:1071/625/699, db.py:928) |
| 巨型文件 (>30KB) | **8 个** (api_routes 148KB / data_fetchers 80KB / debate_routes 49KB / strategy_backtest 43KB / factor_engine 36KB / sector_data 36KB / risk_management 33KB / db 33KB) |
| `print()` 调用 | `api_routes.py` 74 处 / `data_fetchers.py` 354 处 / `db.py` 0 logger |
| 重复 `import` | `concurrent.futures` 在 `api_routes.py:23,48` 重复 2 次 |
| 缺测试的关键模块 | **5 个** (api_routes / data_fetchers / paper_trading / db / ml_predictor) |
| 模型 checkpoint | 3 个 (short 3.5MB / mid 20.7MB / regime 4.8MB),**无训练日期** |
| 检查点漂移风险 | `mid_term_latest.pt` 实际未被任何生产路径调用 |
| 前端 `fetch()` 绕过 `stockAPI` | **18 文件 50+ 处** |
| 巨型页面 (>500行) | **8 个** |

---

## 3. Sprint 路线图 (参考 novel-agent 5 阶段方法)

### Sprint 1: 止血 (1-3 天) — P0 Bug 修复

```
□ [紧急] 修复 api_routes.py 重复 except 块
  → api_routes.py:3017-3024 删除第二个 except
  → 验证: python -c "import api_routes" 成功

□ [资金] paper_trading 风控 fail-closed
  → paper_trading.py:237-240 改为:导入失败 → 进程启动失败
  → 运行时异常 → 熔断+告警,不再静默放行

□ [模型] ml_predictor 版本校验
  → ml_predictor.py:load() 增加 checkpoint metadata 校验
  → 检查 num_features 与 DAILY_FEATURE_NAMES 一致性,不一致抛错
  → 引入 model_registry 表(code → version → sha256 → metrics)

□ [DB] 修复 db2.execute(db2.text()) 错用
  → data_fetchers.py:519 改为 from sqlalchemy import text; db2.execute(text(...))
  → 同时去掉 except: pass,改 logger.error

□ [连接池] signal_fuse 循环 db session 泄漏
  → api_routes.py:2962-2969 改为 with SessionLocal() as db 或 try/finally close

□ [并发] 调度器加锁
  → scheduler.py:_run_task 加 threading.Lock + 任务级 in-flight flag
  → 手动触发检查 in-flight,直接返 409

□ [前端] DatePicker value bug
  → BacktestPage.tsx:140 改为 value={startDate ? dayjs(startDate) : null}

□ [前端] alert() → message 全量替换
  → Strategy/StrategyRecommend/Recommendations/Watchlist 7+ 文件

□ [前端] 加载失败 UI 兜底
  → Watchlist.tsx:82-88 加 isError 渲染分支
```

### Sprint 2: 对齐 (4-6 天) — 架构拆分 + 响应统一

```
□ [核心] 拆分 api_routes.py
  → 按已有模式拆出:
    realtime_routes.py (行情/实时/历史 K线)
    paper_routes.py    (模拟盘)
    watchlist_routes.py (自选股)
    agent_routes.py    (AI 辩论/分析)
    task_routes.py     (盯盘任务/调度器触发)
    sector_routes.py   (板块预测/画像)
    market_routes.py   (大盘研判/指数)
    fundamental_routes.py (基本面/财务)
    factor_routes.py   (因子/ML 评分)
    monitor_routes.py  (监控/告警)
  → 主 api_routes.py 缩到 < 500 行,只保留 Blueprint 注册

□ [统一] 响应格式装饰器
  → 新增 @json_endpoint(schema=...) 装饰器
  → 逐步替换 266 处 jsonify
  → 关键端点先迁移:辩论、模拟盘、回测、API 行情

□ [挂载] rate_limiter 装饰器
  → debate_routes.register_debate_routes 关键 LLM 端点挂 @rate_limit
  → ai_service.deepseek_chat 入口挂 @rate_limit('ai_analyze')
  → 配 Redis 后端或 LRU 上限

□ [熔断] ai_service 重试机制
  → ai_service.py:99-110 重试覆盖 HTTP 5xx/429/529
  → 用 tenacity 库,指数退避 max 5 次

□ [CORS] 白名单
  → api_server.py:25 改为 CORS(app, origins=[...], supports_credentials=True)

□ [健康] /api/health 深检
  → 查 DB 连通性、外部 API ping、调度器状态、磁盘空间
  → 新增 /api/metrics 供 Prometheus 抓取

□ [前端] 收敛 50+ 裸 fetch → stockAPI
  → services/api.ts 补齐所有端点
  → ESLint rule 禁止页面直接 import fetch

□ [前端] 巨型页面拆分
  → PaperDetail.tsx:779 抽出 EquityCurveChart / PositionsTable / OrdersList
  → StockDetail.tsx:675 抽出 7 个 tab 子组件
  → Home.tsx:609 抽出 5 个 section 子组件
```

### Sprint 3: 加固 (7-10 天) — 资金安全 + 数据一致性

```
□ [资金] paper_trading 订单去重 + 行锁
  → 增加 (account_id, code, direction, price, qty, ts_window) 唯一键
  → position.shares 改 SELECT ... FOR UPDATE

□ [回测] 历史 PE 时间序列
  → strategy_backtest.py:296 改为:按季度披露日取历史 PE
  → 修复 look-ahead bias 后重跑所有回测,记录 baseline 偏差

□ [因子] debt_ratio 替换为真实字段
  → factor_engine.py:441 删除启发式公式
  → 从 data_fetchers.get_fundamental_data 取真实 debt_ratio
  → 缺失值留 None,不参与评分

□ [训练-推理] MidTermPredictor 维度对齐
  → ml_predictor.py:79-103 _daily_to_weekly 改为按 8 价+6 基实际切片
  → 或:把模型改为接受 20 维 (与 short 对齐),重训

□ [数据] 单数据源 + 统一缓存层
  → backtest_data vs kline_cache 边界明确(分时 vs 日级)
  → 统一 market_data_cache 表 + TTL
  → 调度器 prefetch 与实时 API 写入路径分离

□ [配置] 业务配置中心化
  → 新增 business_config.yaml (pydantic Settings)
  → 佣金/印花税/批量限额/大盘阈值/策略阈值 全部可配
  → 支持环境变量覆盖

□ [可观测] LLM Token 追踪
  → ai_service.deepseek_chat 成功后写 usage 表
  → SSE done 事件时写 usage 表
  → /api/usage/stats 端点 + 前端用量面板

□ [可观测] structlog 替换 print
  → api_routes.py 74 print → logger.info/debug/error
  → data_fetchers.py 354 print → logger
  → 加 request_id 中间件,关联单次请求所有日志

□ [前端] 每 Route 独立 ErrorBoundary
  → App.tsx:51-73 改为逐 Route 套 Boundary
  → 全局最外层保留兜底

□ [前端] 统一涨跌色 + 字号 token
  → theme.ts 增加 FSize = { xs: 11, sm: 12, ... }
  → 5+ 反向配色文件全局替换
  → 加 dark mode 切换 UI
```

### Sprint 4: 扩展 (10-14 天) — 模型治理 + 新功能

```
□ [模型] Model Registry
  → 新增 model_versions 表(model_id, code, sha256, trained_at, metrics, dataset_hash)
  → ml_predictor.load() 显式选择 active 版本
  → API: GET/PUT /api/ml/active_version

□ [模型] A/B / 影子模式
  → predict_with_dl(code, model_version=None)
  → 配置 shadow_ratio=0.05,5% 流量走新模型,只记录不决策
  → 离线对照指标: IC / 胜率 / Sharpe

□ [模型] 性能监控
  → 新增 monitoring/ml_monitor.py
  → 每日跑: PSI / KS / 滚动 IC / ECE / Brier
  → 阈值越界触发 AlertService

□ [模型] PyTorch 训练器
  → pipeline/train_short_term.py / train_mid_term.py / train_regime.py
  → 时间窗切分 train/val/test
  → 输出 model_id + metrics + dataset_hash 写 registry

□ [回测] Equity curve API + 可视化
  → /api/backtest/equity_curve/<code>/<strategy> 返回时间序列
  → 前端 ECharts/Plotly 渲染

□ [因子] SHAP / Attention rollout
  → short_term_predictor: MultiheadAttention 输出 attn_out 上做 rollout
  → mid_term_predictor: Integrated Gradients attribution
  → /api/ml/explain/<code> 暴露给前端

□ [回测] 校准落地
  → calibration.py:1-43 接入 predict_with_dl() 出口
  → 校准参数随 checkpoint 保存

□ [策略] 策略对比可视化
  → 同坐标 4 条净值曲线叠加 + 滚动 Sharpe
  → /api/strategy/compare?strategies=...

□ [前端] ML 监控面板
  → /monitoring 页面: 模型今日预测 vs 实际 + 漂移曲线
  → 激活版本切换 UI
```

### Sprint 5: 高级 (14-20 天) — 差异化 + 长期

```
□ [策略] 多策略组合优化
  → portfolio_optimizer.py 接入 signal_fusion
  → 输出"建议仓位 + 期望收益 + 风险预算"

□ [因子] 自动特征工程
  → 监控缺失值/重要性低的因子,自动重训剔除
  → 新增因子 A/B

□ [回测] 敏感度扫描 UI
  → /api/backtest/optimize 网格/贝叶斯
  → 前端 3D 曲面 + 等高线

□ [前端] 策略配置 UI
  → /api/strategy/config/<name> GET/PUT
  → 阈值、权重、过滤器可视化编辑

□ [前端] 键盘快捷键 + 命令面板
  → ? 帮助 / / 搜索自选 / g h 跳首页 / c n 创建策略
  → Command+K 命令面板

□ [前端] 移动端响应式
  → Sider 折叠到抽屉
  → 表格横向滚动优化
  → 首页 < 768px 改单列

□ [测试] 端到端覆盖
  → 关键路径集成测试:辩论 → 模拟盘下单 → 持仓更新
  → Playwright e2e: 自选股 CRUD + 触发辩论 + 查看报告

□ [安全] 沙箱执行
  → sector-prediction / breakout-scan 改模块 import 调用
  → 移除 subprocess.run(uv ...) 路径
  → 严格 path 白名单

□ [数据] 分布式缓存
  → Redis 替换 closure 缓存
  → market_outlook / sector_performance 横向扩容可命中

□ [监控] 告警 + 飞书/钉钉推送
  → 风控告警 / 模型漂移 / 调度器失败 → 飞书机器人
```

---

## 4. 技术债务清单

| 项目 | 严重度 | 说明 | 预计工时 |
|------|--------|------|----------|
| api_routes.py 拆分 | 🔴 高 | 148KB / 3208 行,10+ 业务域 | 6h |
| paper_trading 风控 fail-closed | 🔴 高 | 资金安全 | 1h |
| ml_predictor 维度校验 | 🔴 高 | 训练-推理不一致 | 2h |
| rate_limiter 实际挂载 | 🟡 中 | LLM 端点可被刷 | 2h |
| ai_service 5xx/429 重试 | 🟡 中 | 浪费 LLM 资源 | 1h |
| 统一响应格式 | 🟡 中 | 266 处 jsonify | 4h |
| 业务配置中心化 | 🟡 中 | magic number 散落 | 3h |
| print → structlog | 🟡 中 | 428 处 print | 3h |
| 单数据源 + 统一缓存 | 🟡 中 | 三轨数据写入 | 6h |
| 前端 50+ 裸 fetch 收敛 | 🟡 中 | API 分层薄 | 3h |
| 巨型页面拆分 (8 个) | 🟡 中 | 视图-业务耦合 | 8h |
| PaperDetail chart 抽子组件 | 🟢 低 | 779 行内嵌 chart | 1h |
| 前端 ErrorBoundary 拆分 | 🟢 低 | Routes 全包 | 1h |
| 涨跌色统一 | 🟢 低 | 5+ 文件反向 | 1h |
| 字号 token | 🟢 低 | 60+ 硬编码 | 1h |
| dark mode 切换 UI | 🟢 低 | theme.ts 已定义未接入 | 2h |
| .gitignore 清理 | 🟢 低 | .env/.pt/__pycache__ 入库 | 0.5h |
| 集成测试 | 🟡 中 | 5 关键模块 0 覆盖 | 12h |
| 端到端测试 (Playwright) | 🟢 低 | 0 → 5 关键路径 | 8h |
| CORS 白名单 | 🟢 低 | 当前过宽 | 0.5h |
| ONNX Runtime 接入 | 🟢 低 | 当前 eager 模式高 IO | 4h |
| **合计** | | | **~70h** |

---

## 5. 优先级执行矩阵

```
              高影响                                              低影响
高紧急  ┌──────────────────────────────┬──────────────────────────────┐
        │ Sprint 1 (1-3天)            │ Sprint 1 (续)                 │
        │ BUG-01 重复 except 修        │ BUG-UX-08 DatePicker bug      │
        │ BUG-10 风控 fail-closed      │ BUG-UX-05 alert→message       │
        │ BUG-ML-02 维度校验           │ BUG-UX-07 加载失败兜底        │
        │ BUG-02 db2.text 错用         │                              │
        │ BUG-04 db session 泄漏       │                              │
        ├──────────────────────────────┼──────────────────────────────┤
        │ Sprint 2 (4-6天)            │ Sprint 3 (续)                 │
        │ api_routes 拆分              │ structlog 替换                │
        │ 统一响应格式                 │ CORS 白名单                   │
        │ rate_limiter 挂载            │ 涨跌色/字号统一               │
        │ ai_service 5xx 重试          │ ErrorBoundary 拆分            │
        ├──────────────────────────────┼──────────────────────────────┤
        │ Sprint 3 (7-10天)           │ Sprint 5 (14-20天)            │
        │ 资金安全加固                 │ 自动特征工程                  │
        │ 历史 PE 时间序列             │ 移动端响应式                  │
        │ 单数据源 + 统一缓存          │ 端到端测试                    │
        │ 业务配置中心化               │ dark mode 切换                │
        │ LLM Token 追踪              │ ONNX Runtime                  │
低紧急  ├──────────────────────────────┼──────────────────────────────┤
        │ Sprint 4 (10-14天)          │ 持续改进                      │
        │ Model Registry               │ 文档完善                      │
        │ A/B / 影子模式               │ 类型注解补齐                  │
        │ PyTorch 训练器               │ 性能 Profiling                │
        │ SHAP / Attention rollout     │ 沙箱执行                      │
        │ 校准落地                     │ Redis 缓存迁移                │
        │ 回测 equity curve            │ 飞书/钉钉告警                │
        └──────────────────────────────┴──────────────────────────────┘
```

---

## 6. 关键指标 (优化后目标)

| 指标 | 当前值 | Sprint 1 后 | Sprint 3 后 | 终态 |
|------|--------|------------|------------|------|
| **阻断性 bug 数** | ≥11 (P0) | 0 | 0 | 0 |
| **静默 except: pass** | 18 处 | 4 处 (残留 fallback) | 0 | 0 |
| **零日志吞错** | 4 处 | 0 | 0 | 0 |
| **巨型文件 (>30KB) 数** | 8 个 | 7 (拆 api_routes 准备) | 4 | ≤3 |
| **巨型页面 (>500行) 数** | 8 个 | 8 | 4 (PaperDetail/StockDetail 等已拆) | ≤3 |
| **api_routes.py 行数** | 3208 | 3208 | ≤800 (Blueprint 化) | ≤500 |
| **后端测试数** | 18 | 25 | 50 (含 5 关键模块) | 80+ |
| **前端裸 fetch** | 50+ 处 | 50+ | ≤10 | 0 |
| **LLM 端点限流覆盖** | 0% | 0% | 100% | 100% |
| **统一响应覆盖率** | 0% | 0% | 80% | 100% |
| **模型版本管理** | 无 | 元数据校验 | Registry 表 + A/B | 影子 + 漂移监控 |
| **风控 fail-closed** | 否 (P0 风险) | 是 | 是 | 是 |
| **订单去重 + 行锁** | 无 | 无 | 是 | 是 |
| **Token 追踪覆盖** | 0% | 0% | 100% | 100% |
| **回测 look-ahead 偏差** | 系统性高估 | 识别并标注 | 修复 | 季度披露日 PE |
| **可观测性 (深检 health)** | 仅 status:ok | 准备 | DB/API/调度器 | + Prometheus |

---

## 7. 实施注意事项 (来自 novel-agent 经验教训)

参考 novel-agent 的"harness optimization plan"方法论,我们特别强调:

1. **Sprint 1 优先止血,不要"边修边重构"** — 先把 P0 修完,再动 P1。
2. **每 Sprint 必有"测试 + 验证"** — 修 BUG 后必须跑现有测试,确认无 regression。
3. **响应格式统一要分阶段** — 不要一上来替换 266 处,先 1-2 个端点试点。
4. **拆分 api_routes.py 时保留路由兼容** — 老 URL 必须 301/302 到新地址,前端不动。
5. **模型重训/版本切换要"灰度"** — 影子模式 5% 流量起步,72h 离线指标 OK 再升比例。
6. **资金安全改动必须"双轨"** — 新逻辑与旧逻辑并行跑 1 周,对账零差异再切。
7. **可观测性先行** — Sprint 1 末尾先上 structlog + /api/health 深检,后续才有数据回看。

---

## 8. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| api_routes.py 拆分导致路由失效 | 中 | 高 | 保留所有 Blueprint 在主文件注册,渐进迁移 |
| 模型重训引入新 bug | 高 | 高 | 必须先影子模式 72h,A/B 对照 IC 提升才切 |
| 风控 fail-closed 误伤正常单 | 中 | 中 | 灰度开关:KILL_SWITCH=off 时仍放行 + 告警,72h 后默认开 |
| 业务配置化破坏现有 magic number | 中 | 中 | 旧值作为 yaml 默认,新值需 PR review |
| 测试覆盖低导致重构引入新 bug | 高 | 中 | 关键路径补 integration test 优先 |
| 18 个 print 替换为 logger 的工作量被低估 | 中 | 低 | Sprint 3 一次提交,自动化 grep 验证 |

---

## 9. 引用 (代码审计定位)

### 后端 P0
- [api_routes.py:3017-3024](api_routes.py#L3017) — 重复 except
- [data_fetchers.py:519](data_fetchers.py#L519) — db2.text 错用
- [paper_trading.py:237-240](paper_trading.py#L237) — 风控 fail-open
- [api_routes.py:2962-2969](api_routes.py#L2962) — db session 泄漏
- [ml_predictor.py:58-103](ml_predictor.py#L58) — 无版本 + 维度错配
- [factor_engine.py:441](factor_engine.py#L441) — debt_ratio 启发式
- [strategy_backtest.py:296-319](strategy_backtest.py#L296) — 历史 PE 用今日值

### 前端 P0
- `stock_frontend/src/pages/BacktestPage.tsx:140-144` — DatePicker value bug
- `stock_frontend/src/pages/Strategy.tsx:134,206` — alert() 阻塞
- `stock_frontend/src/pages/Watchlist.tsx:82-88` — 加载失败无 UI
- `stock_frontend/src/pages/StockDetail.tsx:115-117` — window 污染
- `stock_frontend/src/components/AIAnalyzeButton.tsx:22-34` — 状态重置缺失

### 架构 P1
- [api_routes.py](api_routes.py) — 148KB,需拆分
- [rate_limiter.py](rate_limiter.py) — 已定义未挂载
- [error_handler.py](error_handler.py) — api_success/api_error 未使用
- [scheduler.py:470-487](scheduler.py#L470) — scheduler_outputs.json 多线程写
- `stock_frontend/src/pages/PaperDetail.tsx:779` — 巨型页面
- `stock_frontend/src/services/api.ts` — 50+ 处裸 fetch 绕过

---

## 附录: 审计方法与统计

本次审计通过 3 个并行子代理完成,覆盖:
- **后端核心**: 11 个 P0 bug、12 个 P1 架构、10 个 P2 体验
- **前端**: 11 个 P0 bug、9 个 P1 架构、10 个 P2 体验
- **ML/策略**: 10 个 P0 bug、11 个 P1 架构、8 个 P2 体验

**总计**: 32 个 P0 + 32 个 P1 + 28 个 P2 = **92 个 actionable findings**

**关键文件统计**:
- 巨型文件 (>30KB): 8 个
- 巨型页面 (>500 行): 8 个
- 静默吞错: 18 处
- 零日志吞错: 4 处
- 后端测试覆盖关键模块: 0/5

---

*计划创建于 2026-06-06,基于 novel-agent 的 5 阶段 Sprint 方法论。建议每周 review 一次进度,每 Sprint 末做 retrospective。*
