# A-Stock Trading — 基于 AI 多 Agent 协同的 A 股交易分析系统
# AI-powered multi-agent trading analysis system for A-share market

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-18.0+-61DAFB.svg)](https://reactjs.org/)
[![License](https://img.shields.io/badge/License-Non--Commercial-red.svg)](LICENSE)

---

## 📖 项目简介

本项目将 **TradingAgents** 多智能体协同辩论架构落地于 **A 股市场**。通过融合互联网公开数据源，配合大语言模型（LLM）的深度分析能力，为投资者提供多维度辅助决策。

系统提供两种交易策略入口：
- ⚡ **短线量化** — 多 Agent 辩论、11 Agent 协同、因子评分、策略回测、模拟盘
- 📊 **中长线交易** — 自选池健康度、仓位计算器、交易日志、信号灯

### ⚠️ 重要提醒
1. **仅供学习交流**：本项目代码仅用于学术研究与技术交流，**严禁商业用途**。
2. **非投资建议**：所有分析结果基于算法和历史数据，**不构成投资建议**。
3. **风险自担**：股市有风险，投资需谨慎。
4. **安全提示**：建议部署在**私有局域网环境**，请勿直接暴露公网。

---

## 🚀 快速启动

### 前置依赖
- Python 3.9+ / Node.js 18+
- **MySQL 9.0+** (本地安装，默认数据库 `stock_trading`)

```bash
# 安装 MySQL (macOS)
brew install mysql && brew services start mysql

# 创建数据库和用户
mysql -u root -e "
  CREATE DATABASE IF NOT EXISTS stock_trading CHARACTER SET utf8mb4;
  CREATE USER IF NOT EXISTS 'stock_user'@'localhost' IDENTIFIED BY 'stock_pass_2024';
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
# DATABASE_URL 默认指向 MySQL，如需切回 SQLite 注释掉即可

# 启动
python3 api_server.py &          # 后端 → http://localhost:35000
cd stock_frontend && npm install && npm run dev  # 前端 → http://localhost:5173
```

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATABASE_URL` | `mysql+pymysql://stock_user:.../stock_trading` | 数据库连接，支持 SQLite/MySQL |
| `API_PORT` | 35000 | API 服务端口 |
| `AUTH_ENABLED` | 0 | 是否启用 API 认证 |
| `OPENAI_API_KEY` | — | OpenAI API Key |
| `DEEPSEEK_API_KEY` | — | DeepSeek API Key |

---

## 📂 项目结构

```
a-stock-trading/
├── api_server.py          # Flask 入口
├── api_routes.py          # 主路由
├── midline_routes.py      # 中长线交易 API
├── ai_service.py          # AI 服务调用
├── config.py              # 共享配置 (API_BASE, DATABASE_URL)
├── models.py              # ORM 模型 (26表, 支持 SQLite/MySQL)
├── db.py                  # CRUD 操作层
├── scheduler.py           # 内置任务调度器
├── data_fetchers.py       # 数据获取层 (基本面上MySQL优先)
├── fundamental_data.py    # 基本面数据模块 (akshare THS)
├── backtest_engine.py     # 回测引擎
├── risk_management.py     # 风险管理
├── ml_predictor.py        # ML 预测
├── error_handler.py       # 统一错误处理
├── retry.py               # 外部 API 重试装饰器
├── ai_config.py           # AI 密钥管理 (env→DB)
├── logging_config.py      # JSON 结构化日志
├── migrate_to_mysql.py    # SQLite→MySQL 迁移脚本
├── fill_missing_data.py   # 日K数据补全 (东方财富 HTTP)
├── pull_watchlist_financials.py  # 自选股财报补全
├── stock_frontend/        # React + Vite 前端
│   ├── src/pages/
│   │   ├── Home.tsx       # 首页大盘
│   │   ├── Midline.tsx    # 中长线看板
│   │   └── StockDetail.tsx # 个股详情 (基本面独立快速加载)
│   ├── src/components/    # 可复用组件
│   └── src/__tests__/     # 前端测试
├── strategies/            # 选股策略 (突破/十倍股)
├── tests/                 # 后端测试
├── openspec/              # OpenSpec 规范文档
│   ├── specs/             # 模块规格
│   └── changes/archive/   # 变更提案归档
├── scripts/               # 定时任务脚本
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── .env                   # 环境变量 (gitignore)
└── .env.example
```

---

## 🔧 Harness — 开发基础设施

### Makefile 命令

| 命令 | 说明 |
|------|------|
| `make dev` | 启动后端+前端 |
| `make test` | 运行后端测试 |
| `make test-frontend` | 运行前端测试 (vitest) |
| `make cov` | 生成覆盖率 HTML 报告 (`htmlcov/index.html`) |
| `make lint` | ruff 代码检查 + TypeScript 类型检查 |
| `make clean` | 清理缓存文件 |

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

所有日志输出 JSON 格式：`{"ts": "...", "level": "INFO", "module": "...", "msg": "..."}`

### AI 密钥管理

```
优先级：环境变量 > DB 存储
  OPENAI_API_KEY=sk-xxx   # 环境变量优先
  DEEPSEEK_API_KEY=sk-xxx
  QWEN_API_KEY=sk-xxx
```

### Docker

```bash
docker compose up          # 后端 :35000 + 前端 :5173
docker compose up -d       # 后台运行
```

---

## 📋 OpenSpec — 规范驱动开发

本项目使用 [OpenSpec](https://openspec.dev/) 进行规范驱动开发 (SDD)。

### 安装

```bash
brew install openspec
cd a-stock-trading && openspec init
```

### 工作流

```bash
# 1. 提出变更
openspec new change <name>
# 编辑 openspec/changes/<name>/design.md   — 设计决策
# 编辑 openspec/changes/<name>/tasks.md    — 实现任务

# 2. 实现代码
# ... coding ...

# 3. 归档
openspec archive <name>
```

### 现有 Specs

| 模块 | 文件 |
|------|------|
| 核心架构 | `openspec/specs/core.md` |
| 行情数据 | `openspec/specs/market-data.md` |
| AI 辩论 | `openspec/specs/ai-analysis.md` |
| 策略回测 | `openspec/specs/strategy.md` |
| 风险/ML | `openspec/specs/risk-ml.md` |
| 模拟盘 | `openspec/specs/paper-trading.md` |
| 调度器 | `openspec/specs/scheduler.md` |
| 前端 UI | `openspec/specs/frontend.md` |

### 历史变更

```bash
openspec/changes/archive/
├── 2026-05-24-init-specs/        # 初始化系统规格文档
├── 2026-05-24-optimize-and-test/ # 代码优化 + 测试
├── 2026-05-24-midline-strategy/  # 中长线交易模块
└── 2026-05-30-sqlite-to-mysql/   # SQLite→MySQL 迁移（26表,127万行）
```

---

## 📡 数据源

| 数据 | 来源 | 协议 | 速度 |
|------|------|------|------|
| 实时行情 | 腾讯 qt.gtimg.cn | HTTP | 实时 |
| 日K线 | 东方财富 push2 + 本地 MySQL backtest_data | HTTP | 批量 3-5s/只 |
| 基本面 | **本地 MySQL stock_financials** → 东方财富 DataCenter | HTTP | <100ms |
| 资金流向 | Sina API | HTTP | 实时 |
| 财务数据批量 | 东方财富 `RPT_F10_FINANCE_MAINFINADATA` | HTTPS | 2-4s/只 |
| 美股 | Yahoo Finance (yfinance) | HTTPS | 实时 |

> macOS Python 3.9 + LibreSSL 环境下，东方财富 HTTPS API 会断连。K线拉取改用 `http://push2his.eastmoney.com`。

---

## 📊 中长线交易模块

专为小资金散户设计，聚焦持仓管理而非全市场扫描。

### 看板功能

| 面板 | API | 说明 |
|------|-----|------|
| 自选池健康度 | `GET /api/midline/watchlist-health` | MA+MACD+RSI 三信号评分 (0-100) |
| 仓位计算器 | `POST /api/midline/position-calc` | 输入止损价 → 建议股数+盈亏比 |
| 交易日志 | `GET/POST /api/midline/journal` | 交易记录 CRUD |
| 交易统计 | `GET /api/midline/journal/stats` | 胜率/盈亏比/连胜连败 |

### 评分算法

```
MA 排列 (40分): MA5>MA20>MA60=多头, MA5>MA20=短期多头
MACD 方向 (30分): 强势多头/多头/金叉初期/死叉
RSI 区间 (30分): 40-70健康, 30-40偏弱, >70超买, <30超卖
```

---

## 🧠 短线量化 — 多 Agent 辩论系统

### 专家角色
- 技术分析 / 资金流 / 基本面 / 舆情 / 行业对比
- 看多 Agent / 看空 Agent（辩论双方）
- 日内做T / 超短线 / 龙头分歧低吸

### 辩论流程
1. 独立分析 (1-3 轮) → 2. 交叉辩论 (1-3 轮) → 3. Operator 生成报告

### 量化功能
- 21 因子评分 + RF/规则 ML 预测
- 4 策略回测 (MA/RSI/MACD/布林) + 5 场景预测
- VaR/CVaR/夏普/凯利 风险管理
- 模拟盘 + 买卖计划 + ETF 替代

---

## ⭐ Star History

[![Star History Chart](https://api.star-history.com/svg?repos=DLWangSan/a-stock-trading&type=date&legend=bottom-right)](https://www.star-history.com/#DLWangSan/a-stock-trading&type=date&legend=bottom-right)

---

## ⚖️ 免责声明

1. **投资风险**：本软件仅用于数据分析参考，不对任何投资结果负责。
2. **版权声明**：Non-Commercial License — 禁止商业售卖、封装付费服务。
3. **数据说明**：通过互联网公开接口融合多方信息，版权归原提供平台所有。

---

*If you find this project helpful, please give us a ⭐!*
