# Frontend — React UI

## 技术栈

| 项目 | 版本 |
|------|------|
| React | 19.2 |
| Vite | 7.3 |
| TypeScript | 5.9 |
| Ant Design | 5.x |
| React Router | 7.12 |
| TanStack Query | 5.90 |
| lightweight-charts | 4.2 |
| Zustand | 5.0 |

## 路由与页面 (全 antd 重构)

| 路由 | 组件 | 状态 |
|------|------|------|
| `/` | Home.tsx | ✅ antd |
| `/watchlist` | Watchlist.tsx | ✅ antd |
| `/stock/:code` | StockDetail.tsx | ✅ antd |
| `/paper` | PaperAccounts.tsx | ✅ antd |
| `/paper/:id` | PaperDetail.tsx | ✅ antd |
| `/paper/rankings` | PaperRankings.tsx | ✅ antd |
| `/paper/breakdown/:id` | PaperBreakdown.tsx | ✅ antd |
| `/backtest` | BacktestPage.tsx | ✅ antd |
| `/strategy` | StrategyRecommend.tsx | ✅ antd |
| `/strategies` | StrategyLibrary.tsx | ✅ antd |
| `/strategies/:id/run` | StrategyRun.tsx | ✅ antd |
| `/tasks` | Tasks.tsx | ✅ antd |
| `/ai-debate` | AIDebate.tsx | ✅ antd |
| `/settings` | Settings.tsx | ✅ antd |
| `/sector-prediction` | SectorPrediction.tsx | ✅ antd |
| `/recommendations` | Recommendations.tsx | ✅ antd |
| `/midline` | Midline.tsx | ✅ antd |

## 共享组件

| 组件 | 状态 |
|------|------|
| Layout | antd Sider + Menu + Segmented |
| IndexCard | antd Card + Statistic |
| ErrorBoundary | antd Result |
| EmptyState | antd Empty |
| StockHeader | antd Descriptions + Statistic |
| StockAnalysis | antd Card + Table |
| StockDebate | antd Card + Table + Tag |
| AIAnalyzeButton | antd Button + Modal |
| TradeModal | antd Modal + Form |
| ApplyToPaperPanel | antd Modal + Form |
| CandlestickChart | lightweight-charts (不变) |
| MLPredictPanel | antd Card + Row/Col |
| RiskPanel | antd Card + Row/Col |
| MoneyFlowPanel | antd Card + Row/Col |

## 状态管理

| Store | 内容 |
|-------|------|
| configStore (Zustand persist) | API URL, AI keys |
| watchlistStore | 自选股列表 |

## 配置

| 方式 | 文件 |
|------|------|
| Vite 代理 | vite.config.ts — /api → localhost:35000 |
| API 地址 | .env — VITE_API_BASE_URL |
| antd 主题 | App.tsx ConfigProvider |
| 测试 | Vitest + @testing-library/react + jsdom |

## 测试

- 22 个 test 文件，308 个测试全部通过
- 框架: Vitest + @testing-library/react + @testing-library/jest-dom
- 运行: `RTK_DISABLE=1 npx vitest run`

## 构建

- `npm run build` — Vite 生产构建，输出 dist/
- Bundle: ~1.76MB (gzipped ~540KB)

## New Components (2026-05-30)

### RegimeIndicator
Market state indicator showing bull/bear/sideways with color-coded probability bars and confidence tooltip.

### AgentReasoning
Collapsible panel showing Macro/Technical/Fundamental/Risk agent analysis with stance tags, confidence progress bars, veto flags, and final fusion decision card.

### ValuationPanel
Embedded in StockDetail "定量估值" tab. Industry growth input + composite score ring + core metrics table.

## Midline Panel Upgrades

- DL prediction column in health table (direction + probability + expected return)
- AI risk constraint validation in position calculator
- Inline journal entry form (replaced Modal)
- Server-side pagination for health and journal tables (20/page, 15/page)

## Server-Side Pagination

All list endpoints now support `?page=N&pageSize=M`:

| Endpoint | Default pageSize |
|----------|-----------------|
| `/api/watchlist` | 20 |
| `/api/midline/watchlist-health` | 20 |
| `/api/midline/journal` | 15 |

Frontend Table pagination drives re-fetch via `onChange → state → queryKey change`.
