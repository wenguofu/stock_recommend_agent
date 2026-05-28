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

import PaperRankings from '../pages/PaperRankings';

const mockRankings = [
  {
    account_id: 1, account_name: '策略盘A', strategy_id: 10, initial_capital: 1000000,
    total_value: 1100000, total_pnl: 100000, total_profit_pct: 10.5,
    max_drawdown: -5.2, win_rate: 65.0, stock_count: 5, order_count: 42,
    days_running: 30, created_at: '2025-01-01',
  },
  {
    account_id: 2, account_name: '测试盘B', strategy_id: null, initial_capital: 500000,
    total_value: 460000, total_pnl: -40000, total_profit_pct: -8.0,
    max_drawdown: -12.5, win_rate: 40.0, stock_count: 3, order_count: 20,
    days_running: 15, created_at: '2025-02-01',
  },
  {
    account_id: 3, account_name: '高频策略C', strategy_id: 20, initial_capital: 2000000,
    total_value: 2200000, total_pnl: 200000, total_profit_pct: 8.0,
    max_drawdown: -3.0, win_rate: 55.0, stock_count: 8, order_count: 120,
    days_running: 60, created_at: '2024-12-01',
  },
];

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

describe('PaperRankings', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ rankings: mockRankings }),
    });
  });

  // --- Basic Rendering ---

  it('renders page title "收益排名"', async () => {
    renderWithProviders(<PaperRankings />);
    await waitFor(() => {
      expect(screen.getByText(/收益排名/)).toBeInTheDocument();
    });
  });

  it('renders subtitle', async () => {
    renderWithProviders(<PaperRankings />);
    await waitFor(() => {
      expect(screen.getByText(/按收益率倒序排列/)).toBeInTheDocument();
    });
  });

  it('renders "返回模拟盘" button', async () => {
    renderWithProviders(<PaperRankings />);
    await waitFor(() => {
      expect(screen.getByText(/返回模拟盘/)).toBeInTheDocument();
    });
  });

  // --- Sort Tabs ---

  it('renders sort tabs', async () => {
    renderWithProviders(<PaperRankings />);
    await waitFor(() => {
      expect(screen.getByText('收益率')).toBeInTheDocument();
      expect(screen.getByText('总盈亏')).toBeInTheDocument();
      expect(screen.getByText('胜率')).toBeInTheDocument();
    });
  });

  it('switches sort when tab clicked', async () => {
    const user = userEvent.setup();
    renderWithProviders(<PaperRankings />);
    await waitFor(() => {
      expect(screen.getByText('总盈亏')).toBeInTheDocument();
    });
    await user.click(screen.getByText('总盈亏'));
    // Should re-sort by total_pnl
  });

  // --- Loading State ---

  it('shows loading state initially', () => {
    (fetch as ReturnType<typeof vi.fn>).mockImplementation(
      () => new Promise(() => {})
    );
    renderWithProviders(<PaperRankings />);
    const spin = document.querySelector('.ant-spin');
    expect(spin).toBeTruthy();
  });

  // --- Error State ---

  it('shows error message on fetch failure', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Network error'));
    renderWithProviders(<PaperRankings />);
    await waitFor(() => {
      expect(screen.getByText(/加载失败/)).toBeInTheDocument();
    });
  });

  // --- Empty State ---

  it('shows empty state when no rankings', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ rankings: [] }),
    });
    renderWithProviders(<PaperRankings />);
    await waitFor(() => {
      expect(screen.getByText(/暂无模拟盘数据/)).toBeInTheDocument();
    });
  });

  // --- Table Data ---

  it('renders account names in table', async () => {
    renderWithProviders(<PaperRankings />);
    await waitFor(() => {
      expect(screen.getByText('策略盘A')).toBeInTheDocument();
      expect(screen.getByText('测试盘B')).toBeInTheDocument();
      expect(screen.getByText('高频策略C')).toBeInTheDocument();
    });
  });

  it('renders ranking positions (medals for top 3)', async () => {
    renderWithProviders(<PaperRankings />);
    await waitFor(() => {
      expect(screen.getByText('🥇')).toBeInTheDocument();
      expect(screen.getByText('🥈')).toBeInTheDocument();
      expect(screen.getByText('🥉')).toBeInTheDocument();
    });
  });

  it('renders profit percentages', async () => {
    renderWithProviders(<PaperRankings />);
    await waitFor(() => {
      expect(screen.getByText('+10.50%')).toBeInTheDocument();
      expect(screen.getByText('-8.00%')).toBeInTheDocument();
      expect(screen.getByText('+8.00%')).toBeInTheDocument();
    });
  });

  it('renders total values', async () => {
    renderWithProviders(<PaperRankings />);
    await waitFor(() => {
      // 1,100,000 = 110.00万
      expect(screen.getByText(/110.00万/)).toBeInTheDocument();
    });
  });

  it('renders strategy/manual badges', async () => {
    renderWithProviders(<PaperRankings />);
    await waitFor(() => {
      const strategyBadges = screen.getAllByText('策略盘');
      expect(strategyBadges.length).toBeGreaterThanOrEqual(2);
    });
  });

  it('renders "手动盘" for accounts without strategy', async () => {
    renderWithProviders(<PaperRankings />);
    await waitFor(() => {
      expect(screen.getByText('手动盘')).toBeInTheDocument();
    });
  });

  it('renders win rates', async () => {
    renderWithProviders(<PaperRankings />);
    await waitFor(() => {
      expect(screen.getByText('+65.00%')).toBeInTheDocument();
      expect(screen.getByText('+40.00%')).toBeInTheDocument();
    });
  });

  it('renders max drawdowns', async () => {
    renderWithProviders(<PaperRankings />);
    await waitFor(() => {
      expect(screen.getByText('-5.20%')).toBeInTheDocument();
    });
  });

  it('renders stock counts', async () => {
    renderWithProviders(<PaperRankings />);
    await waitFor(() => {
      expect(screen.getByText('5')).toBeInTheDocument();
      expect(screen.getByText('3')).toBeInTheDocument();
      expect(screen.getByText('8')).toBeInTheDocument();
    });
  });

  // --- Ant Design Components ---

  it('uses antd Table for rankings', async () => {
    renderWithProviders(<PaperRankings />);
    await waitFor(() => {
      const table = document.querySelector('.ant-table');
      expect(table).toBeTruthy();
    });
  });

  it('uses antd Button for actions', async () => {
    renderWithProviders(<PaperRankings />);
    await waitFor(() => {
      const buttons = document.querySelectorAll('.ant-btn');
      expect(buttons.length).toBeGreaterThanOrEqual(1);
    });
  });

  it('uses antd Spin for loading', () => {
    (fetch as ReturnType<typeof vi.fn>).mockImplementation(
      () => new Promise(() => {})
    );
    renderWithProviders(<PaperRankings />);
    const spin = document.querySelector('.ant-spin');
    expect(spin).toBeTruthy();
  });

  it('uses antd Tag for badges', async () => {
    renderWithProviders(<PaperRankings />);
    await waitFor(() => {
      const tags = document.querySelectorAll('.ant-tag');
      expect(tags.length).toBeGreaterThanOrEqual(1);
    });
  });

  // --- No Tailwind ---

  it('has no Tailwind utility classes', async () => {
    renderWithProviders(<PaperRankings />);
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
