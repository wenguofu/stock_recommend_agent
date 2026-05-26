import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Mock fetch globally
global.fetch = vi.fn();

// Mock useParams
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...(actual as object),
    useParams: () => ({ id: '1' }),
    useNavigate: () => mockNavigate,
  };
});

// Mock TradeModal (has Tailwind, not part of this refactor)
vi.mock('../components/TradeModal', () => ({
  default: ({ onClose, onSuccess }: { accountId: number; onClose: () => void; onSuccess: () => void }) => (
    <div data-testid="trade-modal">
      TradeModal
      <button data-testid="trade-close" onClick={onClose}>Close</button>
      <button data-testid="trade-success" onClick={onSuccess}>Success</button>
    </div>
  ),
}));

// Mock lightweight-charts
vi.mock('lightweight-charts', () => ({
  createChart: () => ({
    addLineSeries: () => ({
      setData: vi.fn(),
    }),
    timeScale: () => ({
      fitContent: vi.fn(),
    }),
    applyOptions: vi.fn(),
    remove: vi.fn(),
  }),
  ColorType: { Solid: 'solid' },
}));

import PaperDetail from '../pages/PaperDetail';

const mockSummary = {
  id: 1,
  name: '策略盘A',
  initial_capital: 1000000,
  cash_balance: 250000,
  total_market_value: 800000,
  total_profit_pct: 5.23,
  max_drawdown: -3.15,
  win_rate: 62.5,
  snapshot_interval: 60,
  position_count: 3,
  snapshot_count: 15,
  order_count: 42,
};

const mockPositions = [
  {
    id: 101, code: '000001', name: '平安银行', shares: 5000,
    avg_cost: 12.30, current_price: 12.50, market_value: 62500,
    profit_pct: 1.63, today_profit_pct: 0.52,
    etf_replaced: false, original_code: null,
  },
  {
    id: 102, code: '688001', name: '科创板ETF', shares: 2000,
    avg_cost: 50.00, current_price: 52.00, market_value: 104000,
    profit_pct: 4.00, today_profit_pct: 1.20,
    etf_replaced: true, original_code: '688001',
  },
  {
    id: 103, code: '600519', name: '贵州茅台', shares: 100,
    avg_cost: 1800.00, current_price: 1850.00, market_value: 185000,
    profit_pct: 2.78, today_profit_pct: -0.50,
    etf_replaced: false, original_code: null,
  },
];

const mockOrders = {
  total: 42,
  orders: [
    { id: 1, code: '000001', name: '平安银行', direction: 'buy', price: 12.30, quantity: 5000, amount: 61500, commission: 0, tax: 0, order_type: 'manual', strategy_run_id: null, note: null, created_at: '2025-03-01T10:00:00Z' },
    { id: 2, code: '600519', name: '贵州茅台', direction: 'sell', price: 1850.00, quantity: 50, amount: 92500, commission: 0, tax: 0, order_type: 'signal', strategy_run_id: 'abc', note: '止盈', created_at: '2025-03-02T14:30:00Z' },
  ],
};

const mockCurve = {
  curve: [
    { snapshot_time: '2025-03-01', total_value: 1000000, cash_balance: 1000000, market_value: 0, daily_pnl: 0, daily_pnl_pct: 0 },
    { snapshot_time: '2025-03-02', total_value: 1050000, cash_balance: 250000, market_value: 800000, daily_pnl: 50000, daily_pnl_pct: 5.0 },
  ],
};

function setupFetchMocks() {
  const mockFetch = fetch as ReturnType<typeof vi.fn>;

  mockFetch.mockImplementation((url: string) => {
    if (url.includes('/summary')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ summary: mockSummary }) });
    }
    if (url.includes('/positions')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ positions: mockPositions }) });
    }
    if (url.includes('/orders')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(mockOrders) });
    }
    if (url.includes('/equity_curve')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(mockCurve) });
    }
    if (url.includes('/plans')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ plans: [] }) });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
  });
}

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

describe('PaperDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupFetchMocks();
  });

  // --- Basic Rendering ---

  it('renders account name in header', async () => {
    renderWithProviders(<PaperDetail />);
    await waitFor(() => {
      expect(screen.getByText('策略盘A')).toBeInTheDocument();
    });
  });

  it('renders "手动交易" button', async () => {
    renderWithProviders(<PaperDetail />);
    await waitFor(() => {
      expect(screen.getByText(/手动交易/)).toBeInTheDocument();
    });
  });

  // --- Loading State ---

  it('shows loading state initially', () => {
    (fetch as ReturnType<typeof vi.fn>).mockImplementation(
      () => new Promise(() => {})
    );
    renderWithProviders(<PaperDetail />);
    const spin = document.querySelector('.ant-spin');
    expect(spin).toBeTruthy();
  });

  // --- Summary Cards ---

  it('renders total asset value', async () => {
    renderWithProviders(<PaperDetail />);
    await waitFor(() => {
      // 250000 + 800000 = 1050000 = 105.00万
      expect(screen.getByText(/105.00万/)).toBeInTheDocument();
    });
  });

  it('renders cash balance', async () => {
    renderWithProviders(<PaperDetail />);
    await waitFor(() => {
      expect(screen.getByText(/25.00万/)).toBeInTheDocument();
    });
  });

  it('renders market value', async () => {
    renderWithProviders(<PaperDetail />);
    await waitFor(() => {
      expect(screen.getByText(/80.00万/)).toBeInTheDocument();
    });
  });

  it('renders total profit percentage', async () => {
    renderWithProviders(<PaperDetail />);
    await waitFor(() => {
      expect(screen.getByText('+5.23%')).toBeInTheDocument();
    });
  });

  // --- Secondary Stats ---

  it('renders initial capital', async () => {
    renderWithProviders(<PaperDetail />);
    await waitFor(() => {
      expect(screen.getByText(/100.00万/)).toBeInTheDocument();
    });
  });

  it('renders max drawdown', async () => {
    renderWithProviders(<PaperDetail />);
    await waitFor(() => {
      expect(screen.getByText('-3.15%')).toBeInTheDocument();
    });
  });

  it('renders win rate', async () => {
    renderWithProviders(<PaperDetail />);
    await waitFor(() => {
      // The Statistic component renders numbers with ant-statistic-content-value
      // Look for the win rate card section
      const winRateElements = screen.getAllByText(/62\.50%?/);
      expect(winRateElements.length).toBeGreaterThanOrEqual(1);
    });
  });

  it('renders snapshot interval', async () => {
    renderWithProviders(<PaperDetail />);
    await waitFor(() => {
      // "60 分钟" text
      const intervalEls = screen.getAllByText(/60/);
      // At least one of them should be next to 分钟
      expect(intervalEls.length).toBeGreaterThanOrEqual(1);
    });
  });

  // --- Positions Table ---

  it('renders positions table', async () => {
    renderWithProviders(<PaperDetail />);
    await waitFor(() => {
      // The Card title contains "持仓"
      const cardTitles = document.querySelectorAll('.ant-card-head-title');
      const hasPositions = Array.from(cardTitles).some(el => el.textContent?.includes('持仓'));
      expect(hasPositions).toBe(true);
    });
  });

  it('renders stock codes in positions', async () => {
    renderWithProviders(<PaperDetail />);
    await waitFor(() => {
      // getAllByText since antd Table may duplicate
      expect(screen.getAllByText('000001').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('688001').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('600519').length).toBeGreaterThanOrEqual(1);
    });
  });

  it('renders stock names in positions', async () => {
    renderWithProviders(<PaperDetail />);
    await waitFor(() => {
      expect(screen.getAllByText('平安银行').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('贵州茅台').length).toBeGreaterThanOrEqual(1);
    });
  });

  it('renders ETF badge for replaced stocks', async () => {
    renderWithProviders(<PaperDetail />);
    await waitFor(() => {
      expect(screen.getAllByText('ETF').length).toBeGreaterThanOrEqual(1);
    });
  });

  // --- Orders Table ---

  it('renders orders table', async () => {
    renderWithProviders(<PaperDetail />);
    await waitFor(() => {
      const cardTitle = document.querySelectorAll('.ant-card-head-title');
      const hasOrders = Array.from(cardTitle).some(el => el.textContent?.includes('交易记录'));
      expect(hasOrders).toBe(true);
    });
  });

  it('renders order direction labels', async () => {
    renderWithProviders(<PaperDetail />);
    await waitFor(() => {
      expect(screen.getAllByText('买入').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('卖出').length).toBeGreaterThanOrEqual(1);
    });
  });

  it('renders pagination controls', async () => {
    renderWithProviders(<PaperDetail />);
    await waitFor(() => {
      const pagination = document.querySelector('.ant-pagination');
      expect(pagination).toBeTruthy();
    });
  });

  // --- Not Found State ---

  it('shows not found when summary is null', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({}),
    });
    renderWithProviders(<PaperDetail />);
    await waitFor(() => {
      expect(screen.getByText(/模拟盘账户不存在/)).toBeInTheDocument();
    });
  });

  // --- Ant Design Components ---

  it('uses antd Card components for summary', async () => {
    renderWithProviders(<PaperDetail />);
    await waitFor(() => {
      const cards = document.querySelectorAll('.ant-card');
      expect(cards.length).toBeGreaterThanOrEqual(4);
    });
  });

  it('uses antd Table for positions', async () => {
    renderWithProviders(<PaperDetail />);
    await waitFor(() => {
      const table = document.querySelector('.ant-table');
      expect(table).toBeTruthy();
    });
  });

  it('uses antd Statistic for summary values', async () => {
    renderWithProviders(<PaperDetail />);
    await waitFor(() => {
      const stats = document.querySelectorAll('.ant-statistic');
      expect(stats.length).toBeGreaterThanOrEqual(1);
    });
  });

  it('uses antd Tag for ETF badge', async () => {
    renderWithProviders(<PaperDetail />);
    await waitFor(() => {
      const tags = document.querySelectorAll('.ant-tag');
      expect(tags.length).toBeGreaterThanOrEqual(1);
    });
  });

  it('uses antd Button for action buttons', async () => {
    renderWithProviders(<PaperDetail />);
    await waitFor(() => {
      const buttons = document.querySelectorAll('.ant-btn');
      expect(buttons.length).toBeGreaterThanOrEqual(1);
    });
  });

  it('uses antd Spin for loading', () => {
    (fetch as ReturnType<typeof vi.fn>).mockImplementation(
      () => new Promise(() => {})
    );
    renderWithProviders(<PaperDetail />);
    const spin = document.querySelector('.ant-spin');
    expect(spin).toBeTruthy();
  });

  // --- No Tailwind ---

  it('has no Tailwind utility classes', async () => {
    renderWithProviders(<PaperDetail />);
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

  // --- Equity Curve Section ---

  it('renders equity curve section', async () => {
    renderWithProviders(<PaperDetail />);
    await waitFor(() => {
      expect(screen.getByText(/收益曲线/)).toBeInTheDocument();
    });
  });

  // --- Plan Modal ---

  it('add plan button exists on positions', async () => {
    renderWithProviders(<PaperDetail />);
    await waitFor(() => {
      const addPlanButtons = screen.getAllByText(/添加计划/);
      expect(addPlanButtons.length).toBeGreaterThanOrEqual(1);
    });
  });
});
