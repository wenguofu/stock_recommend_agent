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
    useParams: () => ({ id: '1' }),
    useNavigate: () => mockNavigate,
  };
});

import PaperBreakdown from '../pages/PaperBreakdown';

const mockBreakdown = {
  account_id: 1,
  account_name: '策略盘A',
  initial_capital: 1000000,
  total_value: 1100000,
  cash_balance: 300000,
  total_pnl: 100000,
  total_profit_pct: 10.5,
  max_drawdown: -5.2,
  win_rate: 65.0,
  stock_count: 3,
  stocks: [
    {
      code: '000001',
      name: '平安银行',
      total_buy: 100000,
      total_sell: 80000,
      buy_count: 3,
      sell_count: 2,
      total_commission: 50,
      total_tax: 25,
      realized_pnl: 15000,
      current_position: 1000,
      current_market_value: 12500,
      current_unrealized_pnl: 2500,
      total_pnl: 17500,
      trade_count: 5,
      trades: [
        { order_id: 1, direction: 'buy', price: 12.30, quantity: 500, amount: 6150, commission: 3, tax: 0, order_type: 'manual', note: null, created_at: '2025-01-15T10:00:00Z' },
        { order_id: 2, direction: 'buy', price: 12.50, quantity: 500, amount: 6250, commission: 3, tax: 0, order_type: 'signal', note: '信号买入', created_at: '2025-01-20T14:00:00Z' },
        { order_id: 3, direction: 'sell', price: 13.00, quantity: 500, amount: 6500, commission: 3, tax: 5, order_type: 'manual', note: '止盈', created_at: '2025-02-01T10:00:00Z' },
        { order_id: 4, direction: 'buy', price: 12.80, quantity: 500, amount: 6400, commission: 3, tax: 0, order_type: 'signal', note: null, created_at: '2025-02-15T14:00:00Z' },
        { order_id: 5, direction: 'sell', price: 12.20, quantity: 500, amount: 6100, commission: 3, tax: 5, order_type: 'manual', note: '止损', created_at: '2025-03-01T10:00:00Z' },
      ],
    },
    {
      code: '600519',
      name: '贵州茅台',
      total_buy: 360000,
      total_sell: 370000,
      buy_count: 2,
      sell_count: 2,
      total_commission: 180,
      total_tax: 90,
      realized_pnl: 10000,
      current_position: 0,
      current_market_value: 0,
      current_unrealized_pnl: 0,
      total_pnl: 10000,
      trade_count: 4,
      trades: [
        { order_id: 6, direction: 'buy', price: 1800.00, quantity: 100, amount: 180000, commission: 90, tax: 0, order_type: 'manual', note: null, created_at: '2025-01-10T10:00:00Z' },
        { order_id: 7, direction: 'buy', price: 1780.00, quantity: 100, amount: 178000, commission: 89, tax: 0, order_type: 'signal', note: null, created_at: '2025-01-25T14:00:00Z' },
        { order_id: 8, direction: 'sell', price: 1850.00, quantity: 100, amount: 185000, commission: 92, tax: 185, order_type: 'manual', note: '止盈', created_at: '2025-02-20T10:00:00Z' },
        { order_id: 9, direction: 'sell', price: 1840.00, quantity: 100, amount: 184000, commission: 92, tax: 184, order_type: 'signal', note: '信号卖出', created_at: '2025-03-05T14:00:00Z' },
      ],
    },
    {
      code: '300750',
      name: '宁德时代',
      total_buy: 200000,
      total_sell: 0,
      buy_count: 1,
      sell_count: 0,
      total_commission: 100,
      total_tax: 0,
      realized_pnl: 0,
      current_position: 1000,
      current_market_value: 220000,
      current_unrealized_pnl: 20000,
      total_pnl: 20000,
      trade_count: 1,
      trades: [
        { order_id: 10, direction: 'buy', price: 200.00, quantity: 1000, amount: 200000, commission: 100, tax: 0, order_type: 'manual', note: null, created_at: '2025-03-10T10:00:00Z' },
      ],
    },
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

describe('PaperBreakdown', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockBreakdown),
    });
  });

  // --- Basic Rendering ---

  it('renders account name', async () => {
    renderWithProviders(<PaperBreakdown />);
    await waitFor(() => {
      expect(screen.getByText('策略盘A')).toBeInTheDocument();
    });
  });

  it('renders "个股盈亏明细" subtitle', async () => {
    renderWithProviders(<PaperBreakdown />);
    await waitFor(() => {
      expect(screen.getByText(/个股盈亏明细/)).toBeInTheDocument();
    });
  });

  it('renders "查看账户详情" button', async () => {
    renderWithProviders(<PaperBreakdown />);
    await waitFor(() => {
      expect(screen.getByText(/查看账户详情/)).toBeInTheDocument();
    });
  });

  it('renders back navigation button', async () => {
    renderWithProviders(<PaperBreakdown />);
    await waitFor(() => {
      const backButtons = document.querySelectorAll('.ant-btn');
      expect(backButtons.length).toBeGreaterThanOrEqual(1);
    });
  });

  // --- Loading State ---

  it('shows loading state initially', () => {
    (fetch as ReturnType<typeof vi.fn>).mockImplementation(
      () => new Promise(() => {})
    );
    renderWithProviders(<PaperBreakdown />);
    const spin = document.querySelector('.ant-spin');
    expect(spin).toBeTruthy();
  });

  // --- Error State ---

  it('shows error state on fetch failure', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({}),
    });
    renderWithProviders(<PaperBreakdown />);
    await waitFor(() => {
      expect(screen.getByText(/数据加载失败/)).toBeInTheDocument();
    });
  });

  // --- Summary Cards ---

  it('renders summary total asset', async () => {
    renderWithProviders(<PaperBreakdown />);
    await waitFor(() => {
      // 1,100,000 = 110.00万
      expect(screen.getByText(/110.00万/)).toBeInTheDocument();
    });
  });

  it('renders summary total PnL', async () => {
    renderWithProviders(<PaperBreakdown />);
    await waitFor(() => {
      // 100,000 = 10.00万 (exact match to avoid matching 110.00万)
      expect(screen.getByText('10.00万', { exact: true })).toBeInTheDocument();
    });
  });

  it('renders summary profit percentage', async () => {
    renderWithProviders(<PaperBreakdown />);
    await waitFor(() => {
      expect(screen.getByText('+10.50%')).toBeInTheDocument();
    });
  });

  it('renders stock count', async () => {
    renderWithProviders(<PaperBreakdown />);
    await waitFor(() => {
      expect(screen.getByText(/3 只/)).toBeInTheDocument();
    });
  });

  // --- Stock Breakdown Entries ---

  it('renders stock codes', async () => {
    renderWithProviders(<PaperBreakdown />);
    await waitFor(() => {
      expect(screen.getByText('000001')).toBeInTheDocument();
      expect(screen.getByText('600519')).toBeInTheDocument();
      expect(screen.getByText('300750')).toBeInTheDocument();
    });
  });

  it('renders stock names', async () => {
    renderWithProviders(<PaperBreakdown />);
    await waitFor(() => {
      expect(screen.getByText('平安银行')).toBeInTheDocument();
      expect(screen.getByText('贵州茅台')).toBeInTheDocument();
      expect(screen.getByText('宁德时代')).toBeInTheDocument();
    });
  });

  it('renders position badges', async () => {
    renderWithProviders(<PaperBreakdown />);
    await waitFor(() => {
      const longBadges = screen.getAllByText(/持仓1000股/);
      expect(longBadges.length).toBeGreaterThanOrEqual(1);
    });
    await waitFor(() => {
      expect(screen.getByText('已清仓')).toBeInTheDocument();
    });
  });

  it('renders total PnL per stock', async () => {
    renderWithProviders(<PaperBreakdown />);
    await waitFor(() => {
      // 17500 = 1.75万
      expect(screen.getByText(/1.75万/)).toBeInTheDocument();
    });
  });

  it('renders trade counts', async () => {
    renderWithProviders(<PaperBreakdown />);
    await waitFor(() => {
      expect(screen.getByText('5次')).toBeInTheDocument();
    });
  });

  it('expands stock details on click', async () => {
    const user = userEvent.setup();
    renderWithProviders(<PaperBreakdown />);
    await waitFor(() => {
      expect(screen.getByText('平安银行')).toBeInTheDocument();
    });
    // Click on the stock header to expand
    const stockHeaders = screen.getAllByText('平安银行');
    await user.click(stockHeaders[0]);
    await waitFor(() => {
      // After expand, should see buy/sell totals
      expect(screen.getByText(/买入总额/)).toBeInTheDocument();
      expect(screen.getByText(/卖出总额/)).toBeInTheDocument();
    });
  });

  it('shows trade records in expanded view', async () => {
    const user = userEvent.setup();
    renderWithProviders(<PaperBreakdown />);
    await waitFor(() => {
      expect(screen.getByText('平安银行')).toBeInTheDocument();
    });
    const stockHeaders = screen.getAllByText('平安银行');
    await user.click(stockHeaders[0]);
    await waitFor(() => {
      // Should see buy/sell labels in trades table
      const buyLabels = screen.getAllByText('买入');
      expect(buyLabels.length).toBeGreaterThanOrEqual(1);
      const sellLabels = screen.getAllByText('卖出');
      expect(sellLabels.length).toBeGreaterThanOrEqual(1);
    });
  });

  // --- Ant Design Components ---

  it('uses antd Card components for summary', async () => {
    renderWithProviders(<PaperBreakdown />);
    await waitFor(() => {
      const cards = document.querySelectorAll('.ant-card');
      expect(cards.length).toBeGreaterThanOrEqual(1);
    });
  });

  it('uses antd Table for trade records', async () => {
    const user = userEvent.setup();
    renderWithProviders(<PaperBreakdown />);
    await waitFor(() => {
      expect(screen.getByText('平安银行')).toBeInTheDocument();
    });
    const stockHeaders = screen.getAllByText('平安银行');
    await user.click(stockHeaders[0]);
    await waitFor(() => {
      const tables = document.querySelectorAll('.ant-table');
      expect(tables.length).toBeGreaterThanOrEqual(1);
    });
  });

  it('uses antd Button for actions', async () => {
    renderWithProviders(<PaperBreakdown />);
    await waitFor(() => {
      const buttons = document.querySelectorAll('.ant-btn');
      expect(buttons.length).toBeGreaterThanOrEqual(1);
    });
  });

  it('uses antd Spin for loading', () => {
    (fetch as ReturnType<typeof vi.fn>).mockImplementation(
      () => new Promise(() => {})
    );
    renderWithProviders(<PaperBreakdown />);
    const spin = document.querySelector('.ant-spin');
    expect(spin).toBeTruthy();
  });

  it('uses antd Tag for position badges', async () => {
    renderWithProviders(<PaperBreakdown />);
    await waitFor(() => {
      const tags = document.querySelectorAll('.ant-tag');
      expect(tags.length).toBeGreaterThanOrEqual(1);
    });
  });

  // --- No Tailwind ---

  it('has no Tailwind utility classes', async () => {
    renderWithProviders(<PaperBreakdown />);
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
