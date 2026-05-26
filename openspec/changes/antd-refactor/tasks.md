# Tasks — Ant Design 重构

## Phase 0: 基础设施

- [ ] 0.1 安装 antd + @ant-design/icons
- [ ] 0.2 配置 antd ConfigProvider (主题 token, 中文 locale, dark/light algorithm)
- [ ] 0.3 安装 @testing-library/react + @testing-library/jest-dom + jsdom
- [ ] 0.4 配置 vitest 支持 React Testing Library
- [ ] 0.5 删除 Tailwind 依赖 (tailwindcss, postcss, autoprefixer, tailwind.config.js, postcss.config.js)
- [ ] 0.6 用 antd App 组件包裹，替换 index.css 中的 Tailwind 指令

## Phase 1: Layout 重构

- [ ] 1.1 写 Layout 组件测试
- [ ] 1.2 用 antd Layout + Menu 重写 Layout.tsx
- [ ] 1.3 策略切换 (短线量化/中长线) 用 antd Segmented
- [ ] 1.4 响应式侧边栏 (Sider collapsible)
- [ ] 1.5 面包屑导航

## Phase 2: 共享组件

- [ ] 2.1 ErrorBoundary 组件 (antd Result)
- [ ] 2.2 StockCard 组件 (antd Card + Statistic)
- [ ] 2.3 IndexCard 组件 (antd Card)
- [ ] 2.4 EmptyState 组件 (antd Empty)
- [ ] 2.5 PageHeader 组件 (antd Typography + Space)

## Phase 3: 首页重构 (Home.tsx)

- [ ] 3.1 写 Home 页面测试
- [ ] 3.2 大盘指数卡片 (antd Row + Col + Card)
- [ ] 3.3 自选股网格 (antd Card grid)
- [ ] 3.4 板块表现面板 (antd Table)
- [ ] 3.5 辩论记录 (antd Table + Tag)
- [ ] 3.6 大盘研判侧栏 (antd Descriptions + Progress)

## Phase 4: 核心页面重构

- [ ] 4.1 StockDetail.tsx (947行 → 目标 <400行)
- [ ] 4.2 Watchlist.tsx
- [ ] 4.3 BacktestPage.tsx
- [ ] 4.4 StrategyLibrary.tsx
- [ ] 4.5 StrategyRun.tsx
- [ ] 4.6 StrategyRecommend.tsx

## Phase 5: 其余页面重构

- [ ] 5.1 Paper 系列 (4页: Accounts, Detail, Rankings, Breakdown)
- [ ] 5.2 Tasks.tsx
- [ ] 5.3 Settings.tsx
- [ ] 5.4 AIDebate.tsx
- [ ] 5.5 SectorPrediction.tsx
- [ ] 5.6 Recommendations.tsx
- [ ] 5.7 Midline.tsx

## Phase 6: 收尾

- [ ] 6.1 全局搜索残留 Tailwind className
- [ ] 6.2 删除 index.css / App.css 中所有 CSS
- [ ] 6.3 全量测试通过
- [ ] 6.4 `npm run build` 成功
- [ ] 6.5 更新 openspec/specs/frontend.md
