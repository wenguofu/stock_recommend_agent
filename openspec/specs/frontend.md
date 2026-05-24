# Frontend — React UI

## 技术栈

| 项目 | 版本 |
|------|------|
| React | 19.2 |
| Vite | 7.2 |
| TypeScript | 5.9 |
| Tailwind CSS | 3.4 |
| React Router | 7.12 |
| TanStack Query | 5.90 |
| lightweight-charts | 4.2 |
| Zustand | 5.0 |
| marked + dompurify | Markdown 渲染 |

## 路由与页面

| 路由 | 组件 | 行数 |
|------|------|------|
| `/` | Home.tsx | 432 |
| `/watchlist` | Watchlist.tsx | — |
| `/stock/:code` | StockDetail.tsx | 947 |
| `/paper` | PaperAccounts.tsx | — |
| `/paper/:id` | PaperDetail.tsx | — |
| `/backtest` | BacktestPage.tsx | — |
| `/strategy` | StrategyRecommend.tsx | — |
| `/strategies` | StrategyLibrary.tsx | — |
| `/tasks` | Tasks.tsx | — |
| `/settings` | Settings.tsx | — |

## 状态管理

| Store | 内容 |
|-------|------|
| `configStore` (Zustand persist) | API URL, AI keys |
| `watchlistStore` | 自选股列表 |

## 子组件 (已提取)

| 组件 | 来源 |
|------|------|
| `MoneyFlowPanel` | StockDetail 拆分 |
| `RiskPanel` | StockDetail 拆分 |
| `MLPredictPanel` | StockDetail 拆分 |
| `CandlestickChart` | K线 + timeline + 分时 |
| `AIAnalyzeButton` | 触发辩论按钮 |
| `TradeModal` | 模拟盘交易弹窗 |
| `ApplyToPaperPanel` | 策略→模拟盘 |
| `LoadingSpinner` | 加载动画 |

## 常量

| 文件 | 内容 |
|------|------|
| `constants/sectorEtfs.ts` | 板块→ETF 映射 + `findEtfs()` |

## 配置

| 方式 | 文件 |
|------|------|
| Vite 代理 | `vite.config.ts` — `/api` → `localhost:35000` |
| API 地址 | `.env` — `VITE_API_BASE_URL` |

## 已知问题

- [ ] 13 个文件中仍有 `import.meta.env.VITE_API_BASE_URL \|\| 'http://127.0.0.1:35000'` 回退（应统一用 proxy 去掉回退）
- [ ] `Home.tsx` 中 `fetchIndexData()` 直接 fetch 不用 stockAPI 类
- [ ] 无错误边界组件 (ErrorBoundary)
- [ ] 无 loading skeleton，全用 spinner
