import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Mock fetch globally
global.fetch = vi.fn();

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...(actual as object),
    useNavigate: () => mockNavigate,
  };
});

import Recommendations from '../pages/Recommendations';

const mockRecs = {
  strategies: {
    youzi: [
      { id: 1, rank: 1, code: '000001', name: '平安银行', price: 12.50, change_pct: 2.3, turnover: 1.5, score: 85, reason: '涨停板突破', strategy: 'youzi', rec_type: 'daily', created_at: '2025-03-01' },
      { id: 2, rank: 2, code: '600519', name: '贵州茅台', price: 1800.00, change_pct: -0.5, turnover: 0.3, score: 72, reason: '资金流入', strategy: 'youzi', rec_type: 'daily', created_at: '2025-03-01' },
    ],
    lianghua: [
      { id: 3, rank: 1, code: '300750', name: '宁德时代', price: 200.00, change_pct: 3.1, turnover: 2.0, score: 90, reason: '多头排列', strategy: 'lianghua', rec_type: 'daily', created_at: '2025-03-01' },
    ],
    jichang: [
      { id: 4, rank: 1, code: '000858', name: '五粮液', price: 150.00, change_pct: 1.2, turnover: 0.8, score: 65, reason: 'RSI超卖', strategy: 'jichang', rec_type: 'daily', created_at: '2025-03-01' },
    ],
  },
};

const mockAccounts = {
  accounts: [
    { id: 1, name: '策略盘A', auto_trade: true },
  ],
};

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

describe('Recommendations', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    const mockFetch = fetch as ReturnType<typeof vi.fn>;
    mockFetch.mockImplementation((url: string) => {
      if (url.includes('/api/recommendations/latest')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(mockRecs) });
      }
      if (url.includes('/api/paper/accounts')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(mockAccounts) });
      }
      if (url.includes('/api/sectors/stock/')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ sector: '银行' }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });
  });

  // --- Basic Rendering ---

  it('renders page title "股票推荐"', async () => {
    renderWithProviders(<Recommendations />);
    await waitFor(() => {
      expect(screen.getByText(/股票推荐/)).toBeInTheDocument();
    });
  });

  it('renders subtitle', async () => {
    renderWithProviders(<Recommendations />);
    await waitFor(() => {
      expect(screen.getByText(/自动筛选潜力股票/)).toBeInTheDocument();
    });
  });

  // --- Tabs ---

  it('renders daily and weekly tabs', async () => {
    renderWithProviders(<Recommendations />);
    await waitFor(() => {
      expect(screen.getByText(/每日推荐/)).toBeInTheDocument();
      expect(screen.getByText(/每周推荐/)).toBeInTheDocument();
    });
  });

  it('switches tab when clicked', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Recommendations />);
    await waitFor(() => {
      expect(screen.getByText(/每周推荐/)).toBeInTheDocument();
    });
    await user.click(screen.getByText(/每周推荐/));
    // Should trigger a new fetch for weekly
    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('type=weekly')
      );
    });
  });

  // --- Generate Button ---

  it('renders "立即生成" button', async () => {
    renderWithProviders(<Recommendations />);
    await waitFor(() => {
      expect(screen.getByText(/立即生成/)).toBeInTheDocument();
    });
  });

  // --- Loading State ---

  it('shows loading state initially', () => {
    (fetch as ReturnType<typeof vi.fn>).mockImplementation(
      () => new Promise(() => {})
    );
    renderWithProviders(<Recommendations />);
    const spin = document.querySelector('.ant-spin');
    expect(spin).toBeTruthy();
  });

  // --- Empty State ---

  it('shows empty state when no strategies', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockImplementation((url: string) => {
      if (url.includes('/api/recommendations/latest')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ strategies: {} }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });
    renderWithProviders(<Recommendations />);
    await waitFor(() => {
      expect(screen.getByText(/暂无推荐数据/)).toBeInTheDocument();
    });
  });

  // --- Strategy Sections ---

  it('renders strategy labels', async () => {
    renderWithProviders(<Recommendations />);
    await waitFor(() => {
      expect(screen.getByText('游资策略')).toBeInTheDocument();
      expect(screen.getByText('量化策略')).toBeInTheDocument();
      expect(screen.getByText('基础工具')).toBeInTheDocument();
    });
  });

  it('renders stock codes in tables', async () => {
    renderWithProviders(<Recommendations />);
    await waitFor(() => {
      expect(screen.getByText('000001')).toBeInTheDocument();
      expect(screen.getByText('600519')).toBeInTheDocument();
      expect(screen.getByText('300750')).toBeInTheDocument();
      expect(screen.getByText('000858')).toBeInTheDocument();
    });
  });

  it('renders stock names', async () => {
    renderWithProviders(<Recommendations />);
    await waitFor(() => {
      expect(screen.getByText('平安银行')).toBeInTheDocument();
      expect(screen.getByText('宁德时代')).toBeInTheDocument();
    });
  });

  it('renders prices', async () => {
    renderWithProviders(<Recommendations />);
    await waitFor(() => {
      expect(screen.getByText('12.50')).toBeInTheDocument();
      expect(screen.getByText('1800.00')).toBeInTheDocument();
    });
  });

  it('renders change percentages', async () => {
    renderWithProviders(<Recommendations />);
    await waitFor(() => {
      expect(screen.getByText('+2.3%')).toBeInTheDocument();
      expect(screen.getByText('-0.5%')).toBeInTheDocument();
    });
  });

  it('renders scores', async () => {
    renderWithProviders(<Recommendations />);
    await waitFor(() => {
      expect(screen.getByText('85')).toBeInTheDocument();
      expect(screen.getByText('90')).toBeInTheDocument();
    });
  });

  it('renders reasons', async () => {
    renderWithProviders(<Recommendations />);
    await waitFor(() => {
      expect(screen.getByText('涨停板突破')).toBeInTheDocument();
    });
  });

  it('renders "跟踪" buttons', async () => {
    renderWithProviders(<Recommendations />);
    await waitFor(() => {
      const trackButtons = screen.getAllByText(/跟踪/);
      expect(trackButtons.length).toBeGreaterThanOrEqual(1);
    });
  });

  // --- Ant Design Components ---

  it('uses antd Table components', async () => {
    renderWithProviders(<Recommendations />);
    await waitFor(() => {
      const tables = document.querySelectorAll('.ant-table');
      expect(tables.length).toBeGreaterThanOrEqual(1);
    });
  });

  it('uses antd Button for actions', async () => {
    renderWithProviders(<Recommendations />);
    await waitFor(() => {
      const buttons = document.querySelectorAll('.ant-btn');
      expect(buttons.length).toBeGreaterThanOrEqual(1);
    });
  });

  it('uses antd Spin for loading', () => {
    (fetch as ReturnType<typeof vi.fn>).mockImplementation(
      () => new Promise(() => {})
    );
    renderWithProviders(<Recommendations />);
    const spin = document.querySelector('.ant-spin');
    expect(spin).toBeTruthy();
  });

  it('uses antd Tag for scores', async () => {
    renderWithProviders(<Recommendations />);
    await waitFor(() => {
      const tags = document.querySelectorAll('.ant-tag');
      expect(tags.length).toBeGreaterThanOrEqual(1);
    });
  });

  // --- No Tailwind ---

  it('has no Tailwind utility classes', async () => {
    renderWithProviders(<Recommendations />);
    await waitFor(() => {
      const allElements = document.querySelectorAll('[class]');
      let hasTailwind = false;
      allElements.forEach((el) => {
        const cls = el.getAttribute('class') || '';
        if (/\b(flex|grid|space-y|space-x|bg-white|bg-gray|bg-blue|bg-red|bg-black|bg-green|bg-yellow|text-gray|text-red|text-green|text-blue|text-yellow|text-center|text-3xl|text-2xl|text-xl|text-lg|text-sm|text-xs|rounded|shadow|p-[0-9]|px-[0-9]|py-[0-9]|m-[0-9]|mb-[0-9]|mt-[0-9]|ml-[0-9]|gap-[0-9]|border-l-4|dark:|hover:bg|transition-colors|animate-spin|divide-y|divide-x|overflow-x-auto)\b/.test(cls)) {
          hasTailwind = true;
        }
      });
      expect(hasTailwind).toBe(false);
    });
  });
});
