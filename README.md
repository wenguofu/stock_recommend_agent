# A-Stock Trading — 基于 AI 多 Agent 协同的 A 股交易分析系统
# AI-powered multi-agent trading analysis system for A-share market

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-18.0+-61DAFB.svg)](https://reactjs.org/)
[![License](https://img.shields.io/badge/License-Non--Commercial-red.svg)](LICENSE)

---

## 📖 项目简介

本项目将 **TradingAgents** 多智能体协同辩论架构落地于 **A 股市场**。通过融合互联网公开数据源，配合大语言模型（LLM）的深度分析能力，为投资者提供多维度辅助决策。

系统提供两种交易策略入口：
- ⚡ **短线量化** — 多 Agent 辩论、12 Agent 协同、因子评分、策略回测、模拟盘
- 📊 **中长线交易** — 自选池健康度、仓位计算器、交易日志、信号灯

### ⚠️ 重要提醒
1. **仅供学习交流**：本项目代码仅用于学术研究与技术交流，**严禁商业用途**。
2. **非投资建议**：所有分析结果基于算法和历史数据，**不构成投资建议**。
3. **风险自担**：股市有风险，投资需谨慎。
4. **安全提示**：建议部署在**私有局域网环境**，请勿直接暴露公网。

---

## ✨ 核心特性

### 🧠 AI 决策
- **12 个 LLM Agent** 多源协同：技术/资金流/基本面/舆情/行业对比 + 看多/看空/日内做T/超短线/龙头分歧低吸/游资情绪
- **多 Agent 辩论** — 独立分析 (1-3 轮) → 交叉辩论 → Operator 生成报告
- 多 LLM 后端：OpenAI / DeepSeek / Qwen / Gemini / Grok

### 📊 选股策略
- **breakout** — 量价/均线突破 (5日新高 + 量能1.5× + RSI<70 + 回撤<10%)
- **tenbagger** — 十倍股筛选 (市值50-500亿 / ROE>10% / 毛利率>25% / 利润增速>20%)
- **zisuye (紫苏叶)** — 产业链"卡脖子"环节选股（大产业链中"小、冷、断供"标的）

### 💰 估值与量化
- **DCF 简易估值** — 5年显式 + Gordon 永续，可调增速/折现率/永续增速三参数
- **20 因子量化评分** (factor_engine v2) + RF/规则 ML 预测
- **量化估值 v2** (Sprint 7) — 动量维度 + 相对市场强度 + DCF 锚定评分卡
- **forward PE / PEG / 成长股分类**

### 🤖 机器学习 / 深度学习
- **ML 预测器** (Random Forest 等) — 方向 / 收益 / 评分
- **DL 短期预测** (BiLSTM + MultiHeadAttention, 1-5 日)
- **DL 中期预测** (Transformer, 1-4 周)
- **市场状态检测** (Regime Detector, bull/bear/sideways)
- **概率校准** (temperature scaling + isotonic regression)
- **PyTorch → ONNX 导出** (推理加速)

### 📈 模拟盘与组合
- **多账户模拟盘** — 持仓/订单/快照/计划/自动规则
- **ETF 替代** (688 科创板一键切 ETF)
- **投资组合优化** — Markowitz / Efficient Frontier / Risk Parity
- **自动交易规则** (价格区间买入 / 止盈止损 / 最大持仓)

### ⚖️ 风险控制
- VaR / CVaR / 夏普 / 最大回撤
- **动态凯利** (Dynamic Kelly) / 破产概率 / 风险平价
- 多止盈策略 / 动态回撤仓位
- Beat the Dealer 投注框架

### 🎯 高胜率推荐 (4 层体系)
1. **Layer 1** — 技术面初筛 (突破/形态/量能)
2. **Layer 2** — 多信号融合评分 (因子 + 资金流 + 舆情)
3. **Layer 3** — 历史胜率回测
4. **Layer 4** — 每日盯盘 + 告警 + 板块热度管理 + 大盘安全过滤

### 🌐 前端 (React 18 + Vite + Antd)
- 25 个页面：首页 / 中线 / 个股详情 / 模拟盘 / 策略库 / 板块预测 / 组合优化 / 回测 / AI 辩论 / 高胜率推荐 / 告警中心 / ML 监控 ...
- 22 个组件：DCF 估值 / 情绪指数 / 关键词云 / 资金流 / 风险面板 / ML 预测 / 市场状态指示 / Cmd+K 命令面板 ...
- 个股详情 9 Tab — 基本面 / 财务趋势 / DCF / K 线+基准 / 形态标注 / 舆情情绪 / 资金流 / 估值 / 关联

---

## 🚀 快速启动

### 前置依赖
- Python 3.9+ / Node.js 18+
- **MySQL 9.0+** (本地安装，默认数据库 `stock_trading`)

```bash
# 安装 MySQL (macOS)
brew install mysql && brew services start mysql

# 创建数据库和用户 (⚠️  把 <your-strong-password> 改成自己的强密码, 不要用示例值)
mysql -u root -e "
  CREATE DATABASE IF NOT EXISTS stock_trading CHARACTER SET utf8mb4;
  CREATE USER IF NOT EXISTS 'stock_user'@'localhost' IDENTIFIED BY '<your-strong-password>';
  GRANT ALL PRIVILEGES ON stock_trading.* TO 'stock_user'@'localhost';
"

# 克隆项目
git clone git@github.com:wenguofu/stock_recommend_agent.git
cd a-stock-trading

# 安装 Python 依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 AI 密钥（优先级高于 DB 存储）
# DATABASE_URL 必填 (MySQL DSN), 密码用上一步设置的强密码, 不要用示例值
# 未设或非 MySQL 启动直接报错

# 启动
python3 api_server.py &          # 后端 → http://localhost:35000
cd stock_frontend && npm install && npm run dev  # 前端 → http://localhost:5173
```

### 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `DATABASE_URL` | ✅ | MySQL DSN (`mysql+pymysql://...`)，未设启动报错 |
| `API_PORT` | — | API 服务端口 (默认 35000) |
| `AUTH_ENABLED` | — | 是否启用 API 认证 (0/1) |
| `OPENAI_API_KEY` | — | OpenAI / DeepSeek / Qwen / Gemini / Grok 等 LLM 密钥 (env 优先 > DB) |

---

## 🏗️ 项目结构

```
a-stock-trading/
├── api_server.py              # Flask 入口 (注册所有 blueprint)
├── config.py                  # 共享配置 (API_BASE, DATABASE_URL)
├── models.py                  # ORM 29 表 (MySQL only, fail-fast)
├── db.py                      # CRUD 操作层 (~1100 行)
│
├── api_routes.py              # 主路由 (watchlist/config/agents/strategies/paper/screening/...)
├── risk_routes.py             # 风控 + 组合优化 (Kelly/止损/风险平价/...)
├── factor_routes.py           # 因子 + ML (exposure/predict/direction/rating_v2)
├── valuation_routes.py        # 估值 forecast/quick/detail
├── midline_routes.py          # 中线 (watchlist-health/position-calc/journal/signals)
├── sector_routes.py           # 板块预测 + 突破扫描 + 股票画像
├── portfolio_routes.py        # 组合优化 (Markowitz/Frontier/Risk Parity)
├── scheduler_routes.py        # 任务调度状态
├── realtime_routes.py         # 实时行情/资金流/情绪 (Sina)
├── debate_routes.py           # AI 辩论 (start/status/stop/jobs)
├── strategy_routes.py         # 策略 (run/validate/backtest/zisuye/...)
├── websocket_routes.py        # WS 推送
│
├── strategies/                # 选股策略
│   ├── breakout.py            #   突破
│   ├── tenbagger.py           #   十倍股
│   └── zisuye.py              #   紫苏叶 (产业链卡脖子)
│
├── services/                  # 业务服务层
│   ├── dcf.py                 #   DCF 估值
│   ├── pattern_detect.py      #   K线形态检测 (5类)
│   └── text_mining.py         #   关键词 + 情绪指数
│
├── llm_agents/                # AI Agent 框架
│   ├── agent_base.py          #   TradingAgent 基类
│   ├── agent_orchestrator.py  #   多 Agent 编排
│   └── agent_prompts/         #   5 个 prompt 模板
│
├── dl_models/                 # 深度学习
│   ├── short_term_predictor.py    # BiLSTM+Attention (1-5日)
│   ├── mid_term_predictor.py      # Transformer (1-4周)
│   ├── regime_detector.py         # 市场状态分类
│   ├── features.py                # DL 特征工程
│   ├── calibration.py             # 概率校准
│   └── onnx_export.py             # ONNX 转换
│
├── quant_valuation.py         # 量化估值 v2 (Sprint 7)
├── factor_engine.py           # 20 因子评分 v2
├── ml_predictor.py            # ML 预测器 (Random Forest)
├── portfolio_optimizer.py     # 组合优化核心
├── backtest_engine.py         # 回测引擎
├── data_fetchers.py           # 数据获取 (akshare/sina/eastmoney)
├── ai_service.py / ai_config.py / business_config.py  # AI/业务配置
│
├── risk_control/              # 风控模块
├── screening/                 # 4 层高胜率筛选
├── pipeline/                  # ML 训练 pipeline
├── market_monitor.py          # 大盘监控
├── task_scheduler.py          # 任务调度器
├── scheduler.py               # 入口
│
├── scripts/                   # 定时任务 (mcp/cdp/fetch_fundamentals/...)
│
├── stock_frontend/            # React 18 + Vite + Antd
│   ├── src/pages/             #   25 个页面
│   ├── src/components/        #   22 个组件 + charts/
│   ├── src/hooks/             #   useApiUrl 等
│   └── src/__tests__/         #   vitest
│
├── tests/                     # 后端测试 (34 个文件)
│   ├── e2e/                   #   Playwright E2E
│   └── test_*.py              #   unit + integration
│
├── openspec/                  # OpenSpec 规范驱动开发
│   ├── specs/                 #   10 个能力规格
│   └── changes/               #   进行中 + 归档变更
│
├── Dockerfile                 # multi-stage (backend + frontend-dev)
├── docker-compose.yml
├── Makefile
├── .env.example               # 模板 (gitignore .env)
└── README.md
```

---

## 🧩 功能模块

### 📊 中长线交易 (Midline)
专为小资金散户设计，聚焦持仓管理而非全市场扫描。

| 面板 | API | 说明 |
|------|-----|------|
| 自选池健康度 | `GET /api/midline/watchlist-health` | MA+MACD+RSI 三信号评分 (0-100) |
| 仓位计算器 | `POST /api/midline/position-calc` | 输入止损价 → 建议股数+盈亏比 |
| 交易日志 | `GET/POST /api/midline/journal` | 交易记录 CRUD |
| 交易统计 | `GET /api/midline/journal/stats` | 胜率/盈亏比/连胜连败 |
| 中线信号 | `GET /api/midline/signals/<code>` | 买卖信号灯 |

**评分算法**：
```
MA 排列 (40分): MA5>MA20>MA60=多头, MA5>MA20=短期多头
MACD 方向 (30分): 强势多头/多头/金叉初期/死叉
RSI 区间 (30分): 40-70健康, 30-40偏弱, >70超买, <30超卖
```

### ⚡ 短线量化 — 多 Agent 辩论
**12 个 Agent 角色**：
- 分析型：技术分析 / 资金流 / 基本面 / 舆情 / 行业对比
- 立场型：看多 Agent / 看空 Agent
- 时机型：日内做T / 复盘 / 超短线 / 龙头分歧低吸 / 游资情绪

**辩论流程**：1. 独立分析 (1-3 轮) → 2. 交叉辩论 (1-3 轮) → 3. Operator 生成报告

**配套量化能力**：
- 20 因子评分 + RF/规则 ML 预测
- 选股策略（breakout / tenbagger / zisuye）+ 回测
- VaR/CVaR/夏普/凯利 风险管理
- 模拟盘 + 买卖计划 + ETF 替代

### 💼 模拟盘 (Paper Trading)
- 多账户隔离 + 初始资金配置
- 持仓/订单/快照/盈亏曲线
- 自动交易规则 (价格区间买入 + 止盈止损 + 最大持仓)
- ETF 替代 (688 科创板一键切 ETF)
- 应用策略到模拟盘 (一键跑策略 → 自动下单)

### 📦 投资组合优化
| 端点 | 功能 |
|------|------|
| `POST /api/portfolio/optimize` | Markowitz 均值-方差 |
| `GET  /api/portfolio/efficient_frontier` | 有效前沿 |
| `GET  /api/portfolio/risk_parity` | 风险平价 |
| `POST /api/portfolio/recommend` | 个性化推荐 |
| `POST /api/portfolio/correlation` | 相关性矩阵 |

### ⚖️ 风险控制
- 仓位管理：`/api/risk/position_size` / `/api/risk/drawdown_position` / `/api/risk/dynamic_kelly`
- 止损策略：`/api/risk/multi_stop` (多止盈)
- 组合风险：`/api/risk/portfolio_report` / `/api/risk/ruin` / `/api/risk/edge`
- 投注框架：`/api/risk/beat_the_dealer`

---

## 📡 数据源

| 数据 | 来源 | 协议 | 速度 |
|------|------|------|------|
| 实时行情 | 腾讯 qt.gtimg.cn | HTTP | 实时 |
| 日K线 | 东方财富 push2his + 本地 MySQL backtest_data | HTTP | 批量 3-5s/只 |
| 历史K线 (回测) | AkShare | HTTP | 批量 |
| 基本面 | **本地 MySQL stock_financials** → 东方财富 DataCenter | HTTP | <100ms |
| 资金流向 | Sina API | HTTP | 实时 |
| 财务数据批量 | 东方财富 `RPT_F10_FINANCE_MAINFINADATA` | HTTPS | 2-4s/只 |
| 板块数据 | 东方财富 + AkShare | HTTP | 批量 |
| 舆情 | Sina 财经新闻 + 东方财富股吧 | HTTP | 实时 |
| 美股 | Yahoo Finance (yfinance) | HTTPS | 实时 |
| 加密货币 (utils) | Tushare | HTTP | 实时 |

> macOS Python 3.9 + LibreSSL 环境下，东方财富 HTTPS API 会断连。K线拉取改用 `http://push2his.eastmoney.com`。

**覆盖范围**：3,410 只 A 股（沪深京）+ 行业板块 + 概念板块

---

## 🛠️ 开发

### Makefile 命令

| 命令 | 说明 |
|------|------|
| `make dev` | 启动后端+前端 |
| `make dev-backend` / `make dev-frontend` | 单独启动 |
| `make test` | pytest tests/ -v (34 个测试文件) |
| `make test-frontend` | vitest run |
| `make cov` | 生成覆盖率 HTML (`htmlcov/index.html`) |
| `make lint` | ruff check + tsc --noEmit |
| `make clean` | 清理 `__pycache__` / `.pytest_cache` / `htmlcov` / `.coverage` |

### 测试覆盖 (34 个文件)
- 单元测试：API / DB / 模型 / 策略 / 估值 / 风控 / ML
- 集成测试：E2E 集成 / E2E pipeline / 端到端
- 特殊：`tests/test_engine_factory.py` (引擎工厂 fail-fast) / `tests/test_zisuye.py` (紫苏叶)
- E2E: `tests/e2e/` (Playwright `portal_e2e.py` + `page_tests/` + `run_all.sh`)

> 跑 `make test` 需设置 `TEST_DATABASE_URL`（指向测试 MySQL）。无 MySQL 时需要数据库的测试自动 `pytest.skip`，不会失败 CI。

### 错误处理
所有 API 返回统一 JSON 格式：
```json
{"error": true, "type": "not_found", "message": "资源不存在", "detail": ""}
```
预定义异常类：`AppError`, `NotFoundError`, `BadRequestError`, `ExternalAPIError`

### 外部 API 重试
```python
from retry import retry_on_failure

@retry_on_failure(max_attempts=3, backoff=2)
def fetch_data():
    ...
```

### 结构化日志
所有日志输出 JSON：`{"ts": "...", "level": "INFO", "module": "...", "msg": "..."}`

### AI 密钥管理
```
优先级：环境变量 > DB 存储
  OPENAI_API_KEY=sk-xxx   # 环境变量优先
  DEEPSEEK_API_KEY=sk-xxx
  QWEN_API_KEY=sk-xxx
  GEMINI_API_KEY=sk-xxx
  GROK_API_KEY=sk-xxx
```

### 安全
- `.env` 在 `.gitignore` 内，**不**进版本控制
- 任何 SQL bootstrap 示例密码（如 `stock_user`）都用 `<your-strong-password>` 占位，**不**用真实密码
- LLM 密钥支持 env + DB 双源，env 优先
- `auth_middleware.py` 支持 Bearer Token 鉴权（`AUTH_ENABLED=1` 启用）

### Docker
```bash
docker compose up          # 后端 :35000 + 前端 :5173
docker compose up -d       # 后台运行
```

---

## 📋 OpenSpec — 规范驱动开发

本项目使用 [OpenSpec](https://openspec.dev/) 进行 SDD。新功能/重构先写 `proposal.md` / `design.md` / `tasks.md`，再 TDD 实现，最后 `archive` 归档。

### 工作流
```bash
# 1. 提出变更
openspec new change <name>
# 编辑 openspec/changes/<name>/{proposal,design,tasks}.md

# 2. TDD red → green → refactor (用 openspec 验证每步)

# 3. 归档
openspec archive <name>
```

### 现有 Specs (10 个)

| 能力 | 文件 | 内容 |
|------|------|------|
| 核心 | `openspec/specs/core.md` | API 服务 / 配置 / 错误契约 |
| 行情数据 | `openspec/specs/market-data.md` | 行情/资金流/行业对比 |
| 前端 | `openspec/specs/frontend.md` | K线 markPoint / 组件契约 |
| AI 分析 | `openspec/specs/ai-analysis.md` | Agent / 辩论 / 情绪 |
| 模拟盘 | `openspec/specs/paper-trading.md` | 账户/订单/计划 |
| 策略 | `openspec/specs/strategy.md` | 策略运行/回测/排名 |
| 调度器 | `openspec/specs/scheduler.md` | 任务调度 |
| 风控 | `openspec/specs/risk-control.md` | 仓位/止损/Kelly |
| 风控-ML | `openspec/specs/risk-ml.md` | 风险与 ML 集成 |
| 量化估值 | `openspec/specs/quant-valuation.md` | DCF / forward PE / PEG / 成长股 |

### 历史变更 (归档)
```
openspec/changes/archive/
├── 2026-05-24-init-specs/                       # 初始化系统规格
├── 2026-05-24-optimize-and-test/                # 代码优化 + 测试
├── 2026-05-24-midline-strategy/                 # 中长线交易模块
├── 2026-05-30-sqlite-to-mysql/                  # SQLite→MySQL 迁移 (26表,127万行)
├── 2026-06-10-fix-sina-fallback-amount-zero/    # 修复新浪资金流 fallback=0
└── 2026-06-13-remove-sqlite-only-mysql/         # 彻底移除 SQLite 代码/数据
```

---

## ⚖️ 免责声明

1. **投资风险**：本软件仅用于数据分析参考，不对任何投资结果负责。
2. **版权声明**：Non-Commercial License — 禁止商业售卖、封装付费服务。
3. **数据说明**：通过互联网公开接口融合多方信息，版权归原提供平台所有。

---

*If you find this project helpful, please give us a ⭐!*
