# AI Analysis — 多Agent辩论与决策

## 架构

```
用户请求 → DebateJob (后台线程) → 多轮分析+辩论 → Operator Agent → 最终报告
```

## ai_service.py (295行)

统一 AI 调用层，支持 5 个 Provider：

| Provider | API URL | 超时 |
|----------|---------|------|
| OpenAI | `api.openai.com` | 120s |
| DeepSeek | `api.deepseek.com` | 120s |
| Qwen | — | — |
| Gemini | — | — |
| Grok | — | — |

### API 端点

| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/ai/debate/start/<code>` | POST | 启动辩论 |
| `/api/ai/debate/start_multi` | POST | 多选一辩论 |
| `/api/ai/debate/status/<job_id>` | GET | 轮询状态 |
| `/api/ai/debate/jobs` | GET | 任务列表 |
| `/api/ai/debate/stop/<job_id>` | POST | 终止 |
| `/api/ai/debate/delete/<job_id>` | DELETE | 删除 |
| `/api/ai/analyze/<code>` | POST | 单Agent分析 |

### 请求格式 (启动辩论)

```json
{
  "agent_ids": [1,2,3,4,5,8,9],
  "analysis_rounds": 3,
  "debate_rounds": 3,
  "position": {"shares": 200, "cost": 55.51}
}
```

### 响应格式 (状态轮询)

```json
{
  "status": "running|completed|failed|canceled",
  "progress": 0-100,
  "progress_detail": ["第1轮分析：...", ...],
  "steps": [{phase, round, agent_id, agent_name, content}],
  "report_md": "## 最终报告\n..."
}
```

### 执行机制

- `threading.Thread` 后台执行
- `future.result(timeout=150)` 防单Agent卡死
- 中间步骤截断到 200 字写入 DB
- `canceled` 字段检测终止信号

## init_agents.py

11 个 Agent 的默认 prompt 和配置初始化。

## 已知问题

- [ ] 辩论逻辑耦合在 `api_routes.py` 中（~200行），应提取到独立模块
- [ ] Operator 报告生成逻辑内嵌于路由函数
- [ ] 无辩论重试机制（网络超时后无法恢复）
- [ ] Agent prompt 保存在数据库，版本控制困难

## LLM Agent Decision Layer (llm_agents/)

> Added: 2026-05-30 — Multi-agent architecture for trading decisions

### Architecture

4 specialist agents run concurrently, 1 fusion agent runs sequentially:

| Agent | Role | Key Inputs | Output |
|-------|------|------------|--------|
| Macro | Senior strategist | Index data, sector heatmap, north-bound flow, regime prediction | stance(bullish/neutral/bearish), confidence 0-100 |
| Technical | Quant analyst | DL predictions, factor scores, technical patterns | stance, key signals, confidence |
| Fundamental | Value analyst | PE/PB percentiles, ROE, growth, margins | stance, valuation, quality grade |
| Risk | Risk manager | VaR, CVaR, max DD, Kelly, liquidity | risk grade, position cap, veto flag |
| Fusion | Portfolio manager | All 4 specialist outputs | action(buy/sell/hold/watch), position%, stop-loss, take-profit |

### Decision Rules

1. Risk Agent has veto power — cannot buy when risk grade "high"
2. Buy requires ≥2 agents bullish AND none bearish
3. Confidence < 40 on any 2 agents → downgrade
4. Conflicting signals → prefer lower-risk option
5. Position = Kelly × risk_coefficient × regime_coefficient

### Technical

- Concurrent execution via ThreadPoolExecutor (max_workers=4)
- Structured JSON output via `response_format: json_object`
- 1-hour result cache per stock+data_hash
- Agent prompts in `llm_agents/agent_prompts/`
- Batch analysis with Semaphore concurrency control (max 5 concurrent)
