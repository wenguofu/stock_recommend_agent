# Ant Design 前端重构 实现计划

> **For Hermes:** 使用 subagent-driven-development 逐任务实现，每任务两阶段 review。

**Goal:** 将 stock_frontend 从 Tailwind CSS 重构为 Ant Design 5，保留所有功能和 API 不变。

**Architecture:** antd 全局主题包在 ConfigProvider，Layout 用 antd Layout+Sider，页面内容用 Card/Table/Descriptions 等标准组件。React Query + Zustand 不变。

**Tech Stack:** React 19, antd 5, @ant-design/icons, TypeScript 5.9, Vite 7, Vitest + @testing-library/react, lightweight-charts

---

### Task 0.1: 安装 antd 依赖

**Objective:** 安装 antd 和 testing-library 全家桶

**Files:**
- Modify: `stock_frontend/package.json`

**Step 1: 安装生产依赖**

```bash
cd stock_frontend && npm install antd @ant-design/icons
```

**Step 2: 安装测试依赖**

```bash
cd stock_frontend && npm install -D @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom
```

**Step 3: 验证安装**

```bash
cd stock_frontend && node -e "require('antd'); console.log('antd OK')"
```

---

### Task 0.2: 配置 vitest 支持 RTL

**Objective:** vitest 能渲染 React 组件做断言

**Files:**
- Modify: `stock_frontend/vite.config.ts`
- Create: `stock_frontend/src/test-setup.ts`

**Step 1: 创建 test-setup.ts**

```typescript
// stock_frontend/src/test-setup.ts
import '@testing-library/jest-dom/vitest';
```

**Step 2: 修改 vite.config.ts — 添加 test 配置**

在 `defineConfig` 中添加：

```typescript
test: {
  globals: true,
  environment: 'jsdom',
  setupFiles: './src/test-setup.ts',
  css: true,
},
```

**Step 3: 运行现有测试验证**

```bash
cd stock_frontend && npx vitest run
```

Expected: 2 test files, all pass (api.test.ts, sectorEtfs.test.ts)

---

### Task 0.3: 创建 antd 主题配置

**Objective:** 统一主题 token，支持 dark/light 切换

**Files:**
- Create: `stock_frontend/src/theme.ts`
- Modify: `stock_frontend/src/App.tsx`

**Step 1: 写失败测试**

```typescript
// stock_frontend/src/__tests__/theme.test.ts
import { describe, it, expect } from 'vitest';
import { lightTheme, darkTheme } from '../theme';

describe('theme', () => {
  it('lightTheme 包含必要 token', () => {
    expect(lightTheme.token).toBeDefined();
    expect(lightTheme.token?.colorPrimary).toBe('#1677ff');
  });

  it('darkTheme 使用暗色算法', () => {
    expect(darkTheme.algorithm).toBeDefined();
  });

  it('两个主题都有 cssVar: true', () => {
    expect(lightTheme.cssVar).toBe(true);
    expect(darkTheme.cssVar).toBe(true);
  });
});
```

Run: `npx vitest run src/__tests__/theme.test.ts`
Expected: FAIL — module not found

**Step 2: 实现 theme.ts**

```typescript
// stock_frontend/src/theme.ts
import type { ThemeConfig } from 'antd';
import { theme } from 'antd';

const { darkAlgorithm } = theme;

const sharedToken = {
  borderRadius: 6,
  fontFamily: `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif`,
};

export const lightTheme: ThemeConfig = {
  cssVar: true,
  token: {
    colorPrimary: '#1677ff',
    ...sharedToken,
  },
};

export const darkTheme: ThemeConfig = {
  cssVar: true,
  algorithm: darkAlgorithm,
  token: {
    colorPrimary: '#1677ff',
    ...sharedToken,
  },
};
```

Run: `npx vitest run src/__tests__/theme.test.ts`
Expected: PASS

**Step 3: 修改 App.tsx — 包裹 ConfigProvider**

```typescript
// stock_frontend/src/App.tsx (关键改动)
import { ConfigProvider, App as AntApp, theme } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { useConfigStore } from './store/configStore';

function App() {
  // TODO: 后续从 store 读取暗色模式
  const isDark = false; // window.matchMedia('(prefers-color-scheme: dark)').matches;

  return (
    <ConfigProvider
      theme={{
        cssVar: true,
        algorithm: isDark ? theme.darkAlgorithm : undefined,
        token: { colorPrimary: '#1677ff', borderRadius: 6 },
      }}
      locale={zhCN}
    >
      <AntApp>
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
            <Layout>
              <Routes>{/* 不变 */}</Routes>
            </Layout>
          </BrowserRouter>
        </QueryClientProvider>
      </AntApp>
    </ConfigProvider>
  );
}
```

**验证:**

```bash
cd stock_frontend && npx vitest run
```

Expected: All tests pass (theme + existing 2 test files)

---

### Task 0.4: 删除 Tailwind 依赖

**Objective:** 清理 Tailwind，但保留文件结构可用

**Files:**
- Modify: `stock_frontend/package.json` (移除依赖)
- Delete: `stock_frontend/tailwind.config.js`
- Delete: `stock_frontend/postcss.config.js`
- Modify: `stock_frontend/src/index.css` (移除 @tailwind 指令)
- Modify: `stock_frontend/src/App.css` (清空)

**Step 1: 移除 npm 包**

```bash
cd stock_frontend && npm uninstall tailwindcss postcss autoprefixer
```

**Step 2: 删除配置文件**

```bash
rm -f stock_frontend/tailwind.config.js stock_frontend/postcss.config.js
```

**Step 3: 重写 index.css — 仅保留基础 reset**

```css
/* stock_frontend/src/index.css */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
```

**Step 4: 清空 App.css**

留空文件（或删除 import）。

**Step 5: 验证 — 暂时会失败（页面还在用 className）**

```bash
cd stock_frontend && npx vitest run
```

---

### Task 1.1: Layout 测试

**Objective:** 先写 Layout 新行为的测试

**Files:**
- Create: `stock_frontend/src/__tests__/Layout.test.tsx`

```typescript
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Layout from '../components/Layout';

// Mock react-router-dom useLocation
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useLocation: () => ({ pathname: '/' }),
  };
});

describe('Layout', () => {
  const renderLayout = (route = '/') => {
    vi.mocked(require('react-router-dom').useLocation).mockReturnValue({ pathname: route });
    return render(
      <MemoryRouter initialEntries={[route]}>
        <Layout>
          <div data-testid="children">content</div>
        </Layout>
      </MemoryRouter>
    );
  };

  it('渲染子内容', () => {
    renderLayout('/');
    expect(screen.getByTestId('children')).toBeInTheDocument();
  });

  it('显示股票交易系统标题', () => {
    renderLayout('/');
    expect(screen.getByText('股票交易系统')).toBeInTheDocument();
  });

  it('显示策略切换按钮', () => {
    renderLayout('/');
    expect(screen.getByText('短线量化')).toBeInTheDocument();
    expect(screen.getByText('中长线交易')).toBeInTheDocument();
  });

  it('短线量化模式下显示量化导航项', () => {
    renderLayout('/');
    expect(screen.getByText('首页')).toBeInTheDocument();
    expect(screen.getByText('自选')).toBeInTheDocument();
  });

  it('中长线模式下显示对应导航', () => {
    renderLayout('/midline');
    expect(screen.getByText('自选池健康度')).toBeInTheDocument();
  });
});
```

Run: `npx vitest run src/__tests__/Layout.test.tsx`
Expected: FAIL — antd Layout 尚未实现

---

### Task 1.2: 用 antd Layout + Menu 重写 Layout

**Objective:** 实现 antd Layout

**Files:**
- Modify: `stock_frontend/src/components/Layout.tsx`

```typescript
import { ReactNode, useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Layout as AntLayout, Menu, Segmented, Typography, theme } from 'antd';
import {
  HomeOutlined, StarOutlined, ExperimentOutlined, ThunderboltOutlined,
  BarChartOutlined, SettingOutlined, OrderedListOutlined, TrophyOutlined,
  ScheduleOutlined, LineChartOutlined, AimOutlined, BulbOutlined,
} from '@ant-design/icons';

const { Header, Sider, Content } = AntLayout;
const { Text } = Typography;

const QUANT_NAV = [
  { path: '/', label: '首页', icon: <HomeOutlined /> },
  { path: '/watchlist', label: '自选', icon: <StarOutlined /> },
  { path: '/paper', label: '模拟盘', icon: <ExperimentOutlined /> },
  { path: '/paper/rankings', label: '收益排名', icon: <TrophyOutlined /> },
  { path: '/recommendations', label: '股票推荐', icon: <BulbOutlined /> },
  { path: '/tasks', label: '任务', icon: <ScheduleOutlined /> },
  { path: '/strategies', label: '策略库', icon: <OrderedListOutlined /> },
  { path: '/strategy', label: '策略推荐', icon: <ThunderboltOutlined /> },
  { path: '/backtest', label: '回测', icon: <BarChartOutlined /> },
  { path: '/sector-prediction', label: '主线预判', icon: <AimOutlined /> },
  { path: '/settings', label: '配置', icon: <SettingOutlined /> },
];

const MIDLINE_NAV = [
  { path: '/midline', label: '自选池健康度', icon: <LineChartOutlined /> },
  { path: '/settings', label: '配置', icon: <SettingOutlined /> },
];

export default function Layout({ children }: { children: ReactNode }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { token } = theme.useToken();
  const isMidline = location.pathname.startsWith('/midline');
  const [strategy, setStrategy] = useState<'quant' | 'midline'>(isMidline ? 'midline' : 'quant');
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    setStrategy(isMidline ? 'midline' : 'quant');
  }, [isMidline]);

  const navItems = strategy === 'midline' ? MIDLINE_NAV : QUANT_NAV;
  const selectedKey = '/' + location.pathname.split('/').slice(1, strategy === 'midline' ? 2 : 3).join('/');
  const resolvedKey = navItems.find(i => i.path === location.pathname)?.path
    || navItems.find(i => location.pathname.startsWith(i.path))?.path
    || '/';

  const switchStrategy = (val: string | number) => {
    const s = val as 'quant' | 'midline';
    setStrategy(s);
    navigate(s === 'midline' ? '/midline' : '/');
  };

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        breakpoint="lg"
        style={{ background: token.colorBgContainer }}
      >
        <div style={{ height: 64, display: 'flex', alignItems: 'center', justifyContent: 'center', borderBottom: `1px solid ${token.colorBorderSecondary}` }}>
          <Text strong style={{ fontSize: collapsed ? 14 : 16, whiteSpace: 'nowrap' }}>
            📈 {collapsed ? '' : '股票交易系统'}
          </Text>
        </div>

        <div style={{ padding: '12px 16px' }}>
          <Segmented
            block
            size="small"
            value={strategy}
            onChange={switchStrategy}
            options={[
              { label: '⚡ 短线', value: 'quant' },
              { label: '📊 中长线', value: 'midline' },
            ]}
          />
        </div>

        <Menu
          mode="inline"
          selectedKeys={[resolvedKey]}
          items={navItems.map(item => ({
            key: item.path,
            icon: item.icon,
            label: <Link to={item.path}>{item.label}</Link>,
          }))}
          style={{ borderInlineEnd: 'none' }}
        />
      </Sider>

      <AntLayout>
        <Content style={{ padding: 24, background: token.colorBgLayout, minHeight: '100vh' }}>
          {children}
        </Content>
      </AntLayout>
    </AntLayout>
  );
}
```

**验证:**

```bash
npx vitest run src/__tests__/Layout.test.tsx
```

Expected: PASS (5 tests)

---

### Task 2.1: ErrorBoundary 组件

**Objective:** 全局错误边界

**Files:**
- Create: `stock_frontend/src/components/ErrorBoundary.tsx`
- Create: `stock_frontend/src/__tests__/ErrorBoundary.test.tsx`

使用 antd `Result` 组件展示错误状态。

写测试 → 实现 → 验证。

---

### Task 2.2: IndexCard 组件

**Objective:** 用 antd Card + Statistic 替代当前内联的 IndexCard

**Files:**
- Create: `stock_frontend/src/components/IndexCard.tsx`
- Create: `stock_frontend/src/__tests__/IndexCard.test.tsx`

```typescript
// IndexCard.tsx
import { Card, Statistic, Skeleton } from 'antd';
import { ArrowUpOutlined, ArrowDownOutlined } from '@ant-design/icons';

interface IndexCardProps {
  title: string;
  data: { current_price: number; change_percent: number; high: number; low: number; volume: number; yesterday_close: number } | undefined;
  isLoading: boolean;
  color: string; // '#1677ff', '#722ed1', etc.
}

export default function IndexCard({ title, data, isLoading, color }: IndexCardProps) {
  if (isLoading) return <Card><Skeleton active /></Card>;
  if (!data) return <Card><Statistic title={title} value="--" /></Card>;

  const changePercent = data.change_percent ?? 0;
  const isUp = changePercent >= 0;

  return (
    <Card
      style={{ borderTop: `3px solid ${color}` }}
      styles={{ body: { padding: 20 } }}
    >
      <Statistic
        title={title}
        value={data.current_price?.toFixed(2)}
        precision={2}
        valueStyle={{ color: isUp ? '#cf1322' : '#3f8600', fontSize: 28 }}
        prefix={isUp ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
        suffix={
          <span style={{ fontSize: 16, color: isUp ? '#cf1322' : '#3f8600' }}>
            {isUp ? '+' : ''}{changePercent.toFixed(2)}%
          </span>
        }
      />
      <div style={{ display: 'flex', gap: 16, marginTop: 12, fontSize: 12, color: '#666' }}>
        <span>高 {data.high?.toFixed(2) ?? '--'}</span>
        <span>低 {data.low?.toFixed(2) ?? '--'}</span>
        <span>量 {(data.volume / 10000).toFixed(0)}万手</span>
      </div>
    </Card>
  );
}
```

---

### Task 3.1–3.6: Home.tsx 重构

**Objective:** 446行 → ~200行，用 antd 组件替代所有内联 Tailwind

**关键模式:**
- 大盘指数: `Row gutter={[16, 16]}` + `Col span={8}` → 3个 IndexCard
- 自选股: `Row gutter={[16, 16]}` + `Col xs={24} sm={12} lg={8}` → StockCard
- 面板切换: `Tabs` 组件替代手写按钮
- 板块表现: `Table` 组件 (antd Table, 带排序)
- 辩论记录: `Table` + `Tag`
- 大盘研判: `Descriptions` + `Progress`

**Home.tsx 重构后结构:**

```typescript
import { Card, Row, Col, Tabs, Table, Tag, Progress, Segmented } from 'antd';

export default function Home() {
  return (
    <Row gutter={[16, 16]}>
      {/* 侧栏: 大盘研判 */}
      <Col xs={24} lg={6}>
        <MarketOutlookPanel />
      </Col>

      {/* 主内容 */}
      <Col xs={24} lg={12}>
        <Segmented options={[{ label: 'A股', value: 'a' }, { label: '美股', value: 'us' }]} />
        <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
          {indices.map(idx => (
            <Col xs={24} md={8} key={idx.code}>
              <IndexCard {...idx} />
            </Col>
          ))}
        </Row>

        <Card title="自选股" style={{ marginTop: 16 }}>
          <Row gutter={[16, 16]}>
            {filteredItems.map(item => (
              <Col xs={24} sm={12} lg={8} key={item.code}>
                <StockCard code={item.code} name={item.name} />
              </Col>
            ))}
          </Row>
        </Card>

        <Card title="辩论记录" style={{ marginTop: 16 }}>
          <Table columns={debateColumns} dataSource={debateJobs} />
        </Card>
      </Col>

      {/* 右侧: 板块 */}
      <Col xs={24} lg={6}>
        <SectorPanel />
      </Col>
    </Row>
  );
}
```

---

### Phase 4–5: 其余14页

每页遵循同一模式：写测试 → 用 antd 标准组件重写 → 验证。

| 页面 | 主要 antd 组件 |
|------|---------------|
| StockDetail | Descriptions, Tabs, Card, Table, Statistic |
| Watchlist | Table (可拖拽排序), Modal, Form, InputNumber |
| BacktestPage | Card, Table, Select, DatePicker, Button |
| StrategyLibrary | Card grid, Tag, Modal, Form |
| StrategyRun | Form, Select, InputNumber, Table, Result |
| Paper 系列 | Table, Statistic, Tabs, Progress |
| Settings | Form, Input, Select, Button, Divider |
| Tasks | Table, Tag, Modal, Form, TimePicker |
| AIDebate | Steps, Card, Spin, Typography |
| SectorPrediction | Card, Table, Tag, Collapse |
| Midline | Table, Progress, Descriptions, Statistic |

---

### Phase 6: 收尾

**Task 6.1: 清理残留**

```bash
cd stock_frontend && grep -r "className=" src/ --include="*.tsx" | grep -v node_modules
```

确保只有 antd 组件内的 className（antd 内部使用）。

**Task 6.2: 全量测试**

```bash
cd stock_frontend && npx vitest run
```

Expected: 所有测试通过，覆盖率 > 70%。

**Task 6.3: 构建**

```bash
cd stock_frontend && npm run build
```

Expected: 构建成功，无 TypeScript 错误。

**Task 6.4: 更新 spec**

更新 `openspec/specs/frontend.md` 反映新的技术栈。

---

## 执行策略

1. 使用 `subagent-driven-development` 逐 Task dispatch
2. 每个 Task: 写测试(RED) → 验证失败 → 实现(GREEN) → 验证通过 → 提交
3. 每完成一个 Phase，全量跑一次测试
4. Phase 0 是整个重构的基础，必须最先完成
