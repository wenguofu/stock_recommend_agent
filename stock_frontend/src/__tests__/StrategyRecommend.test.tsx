import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Mock the API
const mockGetStrongStocks = vi.fn();
const mockGetAgents = vi.fn();
const mockAddWatchlist = vi.fn();
const mockStartMultiSelectDebate = vi.fn();
const mockGetBaseURL = vi.fn().mockReturnValue('http://localhost:35000');
const mockBatchCreatePlans = vi.fn();

vi.mock('../services/api', () => ({
  stockAPI: {
    getStrongStocks: (...args: any[]) => mockGetStrongStocks(...args),
    getAgents: (...args: any[]) => mockGetAgents(...args),
    addWatchlist: (...args: any[]) => mockAddWatchlist(...args),
    startMultiSelectDebate: (...args: any[]) => mockStartMultiSelectDebate(...args),
    getBaseURL: () => mockGetBaseURL(),
    batchCreatePlans: (...args: any[]) => mockBatchCreatePlans(...args),
  },
}));

// Mock LoadingSpinner
vi.mock('../components/LoadingSpinner', () => ({
  default: ({ text }: { text?: string }) => <div data-testid="loading-spinner">{text || 'Loading...'}</div>,
}));

// Mock fetch for recommendations
const mockRecFetch = vi.fn();
global.fetch = vi.fn((url: string) => {
  if (typeof url === 'string' && url.includes('/api/strategy/recommendations')) {
    return mockRecFetch();
  }
  if (typeof url === 'string' && url.includes('/api/paper/accounts')) {
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({ accounts: [{ id: 1, name: '模拟账户1' }] }),
    });
  }
  return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
}) as any;

// Mock react-router-dom navigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...(actual as object),
    useNavigate: () => mockNavigate,
  };
});

// Mock antd message
vi.mock('antd', async () => {
  const actual = await vi.importActual('antd');
  return {
    ...(actual as object),
    App: {
      ...((actual as any).App || {}),
      useApp: () => ({ message: { error: vi.fn(), success: vi.fn() } }),
    },
  };
});

import StrategyRecommend from '../pages/StrategyRecommend';

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

describe('StrategyRecommend', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetStrongStocks.mockResolvedValue({
      strategy: 'strong_stocks',
      description: '强势股接力',
      params: { limit_time: '11:30' },
      trade_dates: { T: '2025-01-01', 'T-1': '2024-12-31', 'T-2': '2024-12-30' },
      count: 2,
      stocks: [
        { code: '000001', name: '平安银行', current_price: 12.50, change_percent: 3.2, volume: 1000000, amount: 12500000, industry: '银行', t1_limit_time: '09:35:00', t2_limit_time: '09:32:00', consecutive_days: 2, break_count: 1 },
        { code: '000002', name: '万科A', current_price: 15.80, change_percent: -1.5, volume: 800000, amount: 12640000, industry: '地产', t1_limit_time: '09:40:00', t2_limit_time: '09:45:00', consecutive_days: 1, break_count: 0 },
      ],
    });
    mockRecFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        strategies: [
          {
            strategy: 'tenbagger',
            name: '十倍潜力股',
            description: '寻找十倍潜力股',
            count: 3,
            stocks: [
              { code: '600001', name: '邯郸钢铁', price: 5.20, score: 85, roe: 15.5, gross_margin: 35.2, ret_60d: 12.3, current_price: 5.20 },
              { code: '600002', name: '齐鲁石化', price: 8.90, score: 70, roe: 12.0, gross_margin: 28.5, ret_60d: -3.1, current_price: 8.90 },
              { code: '600003', name: '东北高速', price: 4.50, score: 55, roe: 8.0, gross_margin: 22.0, ret_60d: 1.5, current_price: 4.50 },
            ],
          },
          {
            strategy: 'breakout',
            name: '突破形态',
            description: '技术突破选股',
            count: 1,
            stocks: [
              { code: '600100', name: '同方股份', price: 25.30, score: 78, break_pct: 5.2, vol_ratio: 2.1, rsi: 65, current_price: 25.30 },
            ],
          },
        ],
        timestamp: '2025-01-01T12:00:00',
      }),
    });
    mockGetAgents.mockResolvedValue([
      { id: 1, name: 'Agent A', type: 'default', enabled: true },
      { id: 2, name: 'Agent B', type: 'intraday_t', enabled: true },
    ]);
    mockAddWatchlist.mockResolvedValue({ id: 1, code: '000001', name: '平安银行', sort_order: 1 });
    mockStartMultiSelectDebate.mockResolvedValue({ job_id: 'test-job-123', name: 'multi-select' });
    mockBatchCreatePlans.mockResolvedValue({ success: true });
  });

  // --- Basic rendering ---

  it('renders strategy tabs', async () => {
    renderWithProviders(<StrategyRecommend />);
    await waitFor(() => {
      expect(screen.getByText('强势股接力')).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText('十倍潜力股')).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText('突破形态')).toBeInTheDocument();
    });
  });

  it('renders default tab (tenbagger) data', async () => {
    renderWithProviders(<StrategyRecommend />);
    await waitFor(() => {
      expect(screen.getByText('十倍潜力股')).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText('邯郸钢铁')).toBeInTheDocument();
    });
  });

  it('renders count of matched stocks', async () => {
    renderWithProviders(<StrategyRecommend />);
    await waitFor(() => {
      expect(screen.getByText('筛选结果')).toBeInTheDocument();
    });
  });

  it('shows refresh button', async () => {
    renderWithProviders(<StrategyRecommend />);
    await waitFor(() => {
      expect(screen.getByText('刷新')).toBeInTheDocument();
    });
  });

  // --- Tab switching ---

  it('switches to breakout tab', async () => {
    renderWithProviders(<StrategyRecommend />);
    await waitFor(() => {
      expect(screen.getByText('突破形态')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText('突破形态'));
    await waitFor(() => {
      expect(screen.getByText('同方股份')).toBeInTheDocument();
    });
  });

  it('switches to strong_stocks tab', async () => {
    renderWithProviders(<StrategyRecommend />);
    await waitFor(() => {
      expect(screen.getByText('强势股接力')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText('强势股接力'));
    await waitFor(() => {
      expect(screen.getByText('平安银行')).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText('万科A')).toBeInTheDocument();
    });
  });

  // --- Strong stocks time selector ---

  it('shows time selector for strong_stocks tab', async () => {
    renderWithProviders(<StrategyRecommend />);
    fireEvent.click(screen.getByText('强势股接力'));
    await waitFor(() => {
      expect(screen.getByText('涨停截止')).toBeInTheDocument();
    });
  });

  // --- Loading state ---

  it('shows loading state', async () => {
    // Make the fetch hang
    mockRecFetch.mockReturnValue(new Promise(() => {}));
    renderWithProviders(<StrategyRecommend />);
    await waitFor(() => {
      expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
    });
  });

  // --- Empty state ---

  it('shows empty state when no stocks', async () => {
    mockRecFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        strategies: [{ strategy: 'tenbagger', name: '十倍潜力股', description: '寻找十倍潜力股', count: 0, stocks: [] }],
        timestamp: '2025-01-01T12:00:00',
      }),
    });
    renderWithProviders(<StrategyRecommend />);
    await waitFor(() => {
      expect(screen.getByText(/暂无/)).toBeInTheDocument();
    });
  });

  // --- Watchlist add ---

  it('adds stock to watchlist', async () => {
    renderWithProviders(<StrategyRecommend />);
    await waitFor(() => {
      expect(screen.getByText('邯郸钢铁')).toBeInTheDocument();
    });
    // Find and click 加自选 button
    const addBtns = screen.getAllByText('加自选');
    expect(addBtns.length).toBeGreaterThan(0);
    fireEvent.click(addBtns[0]);
    await waitFor(() => {
      expect(mockAddWatchlist).toHaveBeenCalled();
    });
  });

  // --- Warning message ---

  it('shows disclaimer warning', async () => {
    renderWithProviders(<StrategyRecommend />);
    await waitFor(() => {
      expect(screen.getByText(/不构成投资建议/)).toBeInTheDocument();
    });
  });

  // --- Ant Design components ---

  it('uses antd components', async () => {
    renderWithProviders(<StrategyRecommend />);
    await waitFor(() => {
      const antElements = document.querySelectorAll('[class*="ant-"]');
      expect(antElements.length).toBeGreaterThan(0);
    });
  });

  it('has no Tailwind utility classes', async () => {
    renderWithProviders(<StrategyRecommend />);
    await waitFor(() => {
      const allElements = document.querySelectorAll('[class]');
      let hasTailwind = false;
      allElements.forEach((el) => {
        const cls = el.getAttribute('class') || '';
        if (/\b(flex|grid|space-y|space-x|bg-white|bg-gray|text-gray|text-red|text-green|text-blue|text-center|rounded|shadow|p-[0-9]|px-[0-9]|py-[0-9]|m-[0-9]|mb-[0-9]|mt-[0-9]|gap-[0-9]|text-\[|dark:|from-blue|to-purple|animate-spin|hover:bg|hover:shadow|hover:border|border-\[|opacity-|scale-|shadow-lg|shadow-md|bg-gradient|min-w-full|divide-y|divide-gray)\b/.test(cls)) {
          hasTailwind = true;
        }
      });
      expect(hasTailwind).toBe(false);
    });
  });
});
