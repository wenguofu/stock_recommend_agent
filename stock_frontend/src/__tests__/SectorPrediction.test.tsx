import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Mock the API
vi.mock('../services/api', () => ({
  stockAPI: {
    getSectorPrediction: vi.fn().mockResolvedValue({
      success: true,
      data: {
        report: `# 主线预判报告
日期: 2025-05-20

## 评分汇总

| # | 板块 | 总分 | 供需 | 周期 | 技术 | 政策 | 资金 | 估值 | 评级 |
|---|------|------|------|------|------|------|------|------|------|
| 1 | **新能源** | **72** | 8 | 7 | 9 | 6 | 7 | 8 | S级 |
| 2 | **半导体** | **65** | 7 | 6 | 8 | 5 | 6 | 7 | A级 |
| 3 | **消费电子** | **58** | 6 | 7 | 5 | 4 | 6 | 5 | B级 |

## 详细分析

### 新能源 — 新能源

| 指标 | 得分 | 说明 |
|------|------|------|
| 供需失衡度 | 8/10 | 供给紧张需求旺盛 |
| 周期位置 | 7/10 | 处于上升周期中段 |
| 技术突破 | 9/10 | 固态电池重大突破 |
| 政策催化 | 6/10 | 政策持续支持 |
| 资金信号 | 7/10 | 北向资金持续流入 |
| 估值弹性 | 8/10 | 估值处于合理区间 |

- ✅ Gate1 供需缺口确认
- ✅ Gate2 技术路线可行
- ✅ Gate3 资金认可度高
- ❌ Gate4 无明确政策催化

**领涨标的:** 宁德时代(300750), 比亚迪(002594)
**评级: S级**

### 半导体 — 半导体

| 指标 | 得分 | 说明 |
|------|------|------|
| 供需失衡度 | 7/10 | 芯片需求稳步增长 |
| 周期位置 | 6/10 | 周期底部回升 |
| 技术突破 | 8/10 | 先进制程取得突破 |
| 政策催化 | 5/10 | 政策中性 |
| 资金信号 | 6/10 | 机构开始布局 |
| 估值弹性 | 7/10 | 估值修复空间大 |

- ✅ Gate1 需求增长确定
- ✅ Gate2 国产替代加速
- ❌ Gate3 资金尚未集中
- ❌ Gate4 政策催化不足

**领涨标的:** 中芯国际(688981)
**评级: A级**
`,
      },
    }),
  },
}));

// Mock antd App.useApp
vi.mock('antd', async () => {
  const actual = await vi.importActual('antd');
  return {
    ...(actual as object),
    App: {
      ...(actual as { App: object }).App,
      useApp: () => ({ message: { error: vi.fn(), success: vi.fn() } }),
    },
  };
});

import SectorPrediction from '../pages/SectorPrediction';

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe('SectorPrediction', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // --- Basic Rendering ---

  it('renders the page title', async () => {
    renderWithProviders(<SectorPrediction />);
    await waitFor(() => {
      expect(screen.getByText(/主线预判/)).toBeInTheDocument();
    });
  });

  it('renders the description text', async () => {
    renderWithProviders(<SectorPrediction />);
    await waitFor(() => {
      expect(screen.getByText(/基于六因子\+四关卡模型/)).toBeInTheDocument();
    });
  });

  it('renders the date info', async () => {
    renderWithProviders(<SectorPrediction />);
    await waitFor(() => {
      expect(screen.getByText(/2025-05-20/)).toBeInTheDocument();
    });
  });

  it('renders sector names in table', async () => {
    renderWithProviders(<SectorPrediction />);
    await waitFor(() => {
      expect(screen.getByText('新能源')).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText('半导体')).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText('消费电子')).toBeInTheDocument();
    });
  });

  it('renders rating badges', async () => {
    renderWithProviders(<SectorPrediction />);
    await waitFor(() => {
      // Check that rating tags exist in the table
      const tags = document.querySelectorAll('.ant-tag');
      const tagTexts = Array.from(tags).map(t => t.textContent?.trim());
      expect(tagTexts).toContain('S级');
      expect(tagTexts).toContain('A级');
      expect(tagTexts).toContain('B级');
    });
  });

  it('renders the score table headers', async () => {
    renderWithProviders(<SectorPrediction />);
    await waitFor(() => {
      // Check visible table headers (not hidden measurement divs)
      const headers = document.querySelectorAll('.ant-table-thead th.ant-table-cell');
      const headerTexts = Array.from(headers).map(h => h.textContent?.trim());
      expect(headerTexts).toContain('总分');
      expect(headerTexts).toContain('供需');
      expect(headerTexts).toContain('资金');
    });
  });

  // --- Ant Design components ---

  it('uses antd Table component', async () => {
    renderWithProviders(<SectorPrediction />);
    await waitFor(() => {
      const tables = document.querySelectorAll('.ant-table');
      expect(tables.length).toBeGreaterThan(0);
    });
  });

  it('uses antd Tag components', async () => {
    renderWithProviders(<SectorPrediction />);
    await waitFor(() => {
      const tags = document.querySelectorAll('.ant-tag');
      expect(tags.length).toBeGreaterThan(0);
    });
  });

  it('uses antd Button components', async () => {
    renderWithProviders(<SectorPrediction />);
    await waitFor(() => {
      const buttons = document.querySelectorAll('.ant-btn');
      expect(buttons.length).toBeGreaterThan(0);
    });
  });

  it('uses antd Spin for loading state', async () => {
    const { stockAPI } = await import('../services/api');
    (stockAPI.getSectorPrediction as ReturnType<typeof vi.fn>).mockImplementationOnce(
      () => new Promise(() => {}) // never resolves to show loading
    );
    const queryClient2 = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient2}>
        <MemoryRouter><SectorPrediction /></MemoryRouter>
      </QueryClientProvider>
    );
    await waitFor(() => {
      const spin = document.querySelector('.ant-spin');
      expect(spin).toBeTruthy();
    });
  });

  // --- No Tailwind ---

  it('has no Tailwind utility classes', async () => {
    renderWithProviders(<SectorPrediction />);
    await waitFor(() => {
      const allElements = document.querySelectorAll('[class]');
      let hasTailwind = false;
      allElements.forEach((el) => {
        const cls = el.getAttribute('class') || '';
        if (/\b(flex|grid|space-y|space-x|bg-white|bg-gray|text-gray|text-red|text-green|text-blue|text-center|rounded|shadow|p-6|px-4|py-2|m-[0-9]|mb-4|mt-2|gap-2|dark:)\b/.test(cls)) {
          hasTailwind = true;
        }
      });
      expect(hasTailwind).toBe(false);
    });
  });

  // --- Sectors count ---

  it('shows correct sector count', async () => {
    renderWithProviders(<SectorPrediction />);
    await waitFor(() => {
      expect(screen.getByText(/3 个板块/)).toBeInTheDocument();
    });
  });

  // --- Detail panel on click ---

  it('shows detail panel when a sector is clicked', async () => {
    const { container } = renderWithProviders(<SectorPrediction />);
    // Click on first sector row
    await waitFor(() => {
      const row = screen.getByText('新能源');
      expect(row).toBeInTheDocument();
      row.click();
    });
    await waitFor(() => {
      expect(screen.getByText(/综合评分 72/)).toBeInTheDocument();
    });
  });
});
