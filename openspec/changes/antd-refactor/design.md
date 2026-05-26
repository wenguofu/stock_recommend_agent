# Ant Design 重构 — 前端UI现代化

> OpenSpec: spec-driven | TDD: RED→GREEN→REFACTOR

## Why

当前前端使用 Tailwind CSS 手写所有组件的样式，导致：
- 代码冗长：Home.tsx 446行、StockDetail.tsx 947行，全量样式内联
- 复用度低：相同的卡片、表格、表单样式在多处重复
- 无成熟组件库：缺失表格排序/筛选、分页、日期选择器、抽屉等标准UI模式
- 维护成本高：改一个视觉风格需要改上百个 className

## What Changes

用 Ant Design 5 (antd) 替换 Tailwind CSS 作为主要UI框架：

- **保留不变**: React 19 + Vite + TypeScript + Zustand + React Query + lightweight-charts
- **新增**: antd 5.x, @ant-design/icons
- **新增测试**: @testing-library/react + @testing-library/jest-dom
- **移除**: Tailwind CSS (postcss, autoprefixer, tailwind.config)
- **移除**: 自定义 LoadingSpinner (用 antd Spin 替代)

## Impact

| 影响范围 | 说明 |
|----------|------|
| package.json | +antd, +@ant-design/icons, +@testing-library/react, -tailwindcss, -postcss, -autoprefixer |
| 全部页面 (16个) | Tailwind className → antd 组件 |
| 全部组件 (8个) | 同上 |
| Layout.tsx | antd Layout + Menu 替代当前导航 |
| App.tsx | 包裹 antd ConfigProvider (主题) |
| index.css / App.css | Tailwind 指令删除，改为 antd 主题 token |
| vite.config.ts | 无需改动 |
| API 层 (api.ts) | 无需改动 |
| Store (zustand) | 无需改动 |
| 测试 | 从 vitest 升级到 vitest + @testing-library/react |

## Non-Goals

- 不改后端 API
- 不改数据库 schema
- 不改 Zustand store 结构
- 不替换 lightweight-charts (antd 无 K 线图)

## Risks

| 风险 | 缓解 |
|------|------|
| 大量页面重构可能引入回归 | TDD：每个组件先写测试，再重构 |
| antd bundle 体积大 | antd 5 支持 tree shaking，仅引入用到的组件 |
| 主题迁移 (dark mode) | antd ConfigProvider + algorithm.darkAlgorithm |
| Tailwind 残留样式冲突 | 全局清掉 Tailwind 后逐一验证 |
