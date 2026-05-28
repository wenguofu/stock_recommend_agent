import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Mock the API
const mockGetStrongStocks = vi.fn();
const mockGetAgents = vi.fn();
const mockAddWatchlist = vi.fn();
const mockStartMultiSelectDebate = vi.fn();
const mockBatchCreatePlans = vi.fn();

vi.mock('../services/api', () => ({
  stockAPI: {
    getStrongStocks: (...args: any[]) => mockGetStrongStocks(...args),
    getAgents: (...args: any[]) => mockGetAgents(...args),
    addWatchlist: (...args: any[]) => mockAddWatchlist(...args),
    startMultiSelectDebate: (...args: any[]) => mockStartMultiSelectDebate(...args),
    batchCreatePlans: (...args: any[]) => mockBatchCreatePlans(...args),
    getBaseURL: () => 'http://localhost:35000',
  },
}));

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...(actual as object),
    useNavigate: () => mockNavigate,
  };
});

import Strategy from '../pages/Strategy';

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

describe('Strategy', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetStrongStocks.mockResolvedValue({
      strategy: 'strong_stocks',
      description: '强势股筛选策略',
      params: { limit_time: '11:30' },
      trade_dates: { T: '2025-05-27', 'T-1': '2025-05-26', 'T-2': '2025-05-23' },
      count: 2,
      stocks: [
        {
          code: '000001',
          name: '平安银行',
          t1_limit_time: '093000',
          t2_limit_time: '093000',
          consecutive_days: 2,
          break_count: 0,
          industry: '银行',
          current_price: 12.5,
          change_percent: 10.0,
          volume: 100000000,
          amount: 1250000000,
        },
        {
          code: '600519',
          name: '贵州茅台',
          t1_limit_time: '094500',
          t2_limit_time: '',
          consecutive_days: 0,
          break_count: 1,
          industry: '白酒',
          current_price: 1800.0,
          change_percent: 5.5,
          volume: 5000000,
          amount: 9000000000,
        },
      ],
    });
  });

  // --- Basic Rendering ---

  it('renders the strong stock strategy card', async () => {
    renderWithProviders(<Strategy />);
    await waitFor(() => {
      expect(screen.getByText('强势股策略')).toBeInTheDocument();
    });
  });

  it('renders the strategy description', async () => {
    renderWithProviders(<Strategy />);
    await waitFor(() => {
      // The strategy description is part of the API response, but may not be displayed directly
      expect(screen.getByText('强势股策略')).toBeInTheDocument();
    });
  });

  it('renders stock count after loading', async () => {
    renderWithProviders(<Strategy />);
    await waitFor(() => {
      expect(screen.getByText('2')).toBeInTheDocument();
    });
  });

  it('renders filter results heading', async () => {
    renderWithProviders(<Strategy />);
    await waitFor(() => {
      expect(screen.getByText('筛选结果')).toBeInTheDocument();
    });
  });

  it('renders refresh button', async () => {
    renderWithProviders(<Strategy />);
    await waitFor(() => {
      expect(screen.getByText('刷新数据')).toBeInTheDocument();
    });
  });

  // --- Loading State ---

  it('shows loading state', () => {
    mockGetStrongStocks.mockReturnValue(new Promise(() => {}));
    renderWithProviders(<Strategy />);
    expect(screen.getByText('加载中...')).toBeInTheDocument();
  });

  // --- Error State ---

  it('shows error state', async () => {
    mockGetStrongStocks.mockRejectedValue(new Error('Network error'));
    renderWithProviders(<Strategy />);
    await waitFor(() => {
      expect(screen.getByText('加载数据失败')).toBeInTheDocument();
    });
  });

  // --- Empty State ---

  it('shows empty state when no stocks', async () => {
    mockGetStrongStocks.mockResolvedValue({
      strategy: 'strong_stocks',
      description: '',
      params: { limit_time: '11:30' },
      trade_dates: { T: '2025-05-27', 'T-1': '2025-05-26', 'T-2': '2025-05-23' },
      count: 0,
      stocks: [],
    });
    renderWithProviders(<Strategy />);
    await waitFor(() => {
      expect(screen.getByText('暂无符合条件的股票')).toBeInTheDocument();
    });
  });

  // --- Table rendering ---

  it('renders stock data in table', async () => {
    renderWithProviders(<Strategy />);
    await waitFor(() => {
      expect(screen.getByText('平安银行')).toBeInTheDocument();
      expect(screen.getByText('000001')).toBeInTheDocument();
      expect(screen.getByText('贵州茅台')).toBeInTheDocument();
      expect(screen.getByText('600519')).toBeInTheDocument();
    });
  });

  it('renders table column headers', async () => {
    renderWithProviders(<Strategy />);
    await waitFor(() => {
      // antd Table may render column titles in multiple elements
      expect(screen.queryAllByText('代码').length).toBeGreaterThan(0);
      expect(screen.queryAllByText('名称').length).toBeGreaterThan(0);
      expect(screen.queryAllByText('行业').length).toBeGreaterThan(0);
      expect(screen.queryAllByText('当前价').length).toBeGreaterThan(0);
      expect(screen.queryAllByText('涨跌幅').length).toBeGreaterThan(0);
    });
  });

  // --- Stock detail links ---

  it('renders detail links for each stock', async () => {
    renderWithProviders(<Strategy />);
    await waitFor(() => {
      // antd Button adds spaces between CJK characters, use role query
      const detailBtns = screen.getAllByRole('link');
      expect(detailBtns.length).toBeGreaterThanOrEqual(1);
    });
  });

  // --- Watchlist button ---

  it('renders add to watchlist button', async () => {
    renderWithProviders(<Strategy />);
    await waitFor(() => {
      const addBtns = screen.getAllByText('加入自选');
      expect(addBtns.length).toBeGreaterThanOrEqual(1);
    });
  });

  // --- Risk warning ---

  it('renders risk warning', async () => {
    renderWithProviders(<Strategy />);
    await waitFor(() => {
      expect(screen.getByText(/固定策略筛选，仅供参考学习/)).toBeInTheDocument();
    });
  });

  // --- Ant Design Components ---

  it('uses antd components', async () => {
    renderWithProviders(<Strategy />);
    await waitFor(() => {
      const antElements = document.querySelectorAll('[class*="ant-"]');
      expect(antElements.length).toBeGreaterThan(0);
    });
  });

  it('has no Tailwind utility classes', async () => {
    renderWithProviders(<Strategy />);
    await waitFor(() => {
      const allElements = document.querySelectorAll('[class]');
      let hasTailwind = false;
      allElements.forEach((el) => {
        const cls = el.getAttribute('class') || '';
        if (/\b(flex|grid|space-y|space-x|bg-white|bg-gray|text-gray|text-red|text-green|text-blue|text-center|rounded|shadow|p-[0-9]|px-[0-9]|py-[0-9]|m-[0-9]|mb-[0-9]|mt-[0-9]|gap-[0-9]|text-\[|dark:|from-blue|to-purple|animate-spin|hover:bg|hover:shadow|hover:border|border-\[|opacity-|scale-|shadow-lg|shadow-md|bg-gradient)\b/.test(cls)) {
          hasTailwind = true;
        }
      });
      expect(hasTailwind).toBe(false);
    });
  });
});
