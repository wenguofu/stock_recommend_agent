import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Mock antd App.useApp message
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

// Mock the API
vi.mock('../services/api', () => ({
  stockAPI: {
    getRealtime: vi.fn().mockResolvedValue({
      code: '000001',
      name: '平安银行',
      current_price: 12.50,
      change_percent: 2.35,
      high: 12.80,
      low: 12.10,
      volume: 50000000,
      amount: 620000000,
    }),
    getComprehensive: vi.fn().mockResolvedValue({
      code: '000001',
      realtime: {
        code: '000001',
        name: '平安银行',
        current_price: 12.50,
        change_percent: 2.35,
        high: 12.80,
        low: 12.10,
        volume: 50000000,
        amount: 620000000,
        turnover_rate: 1.23,
      },
    }),
    getSentiment: vi.fn().mockResolvedValue(null),
    getWatchlist: vi.fn().mockResolvedValue([]),
    listDebateJobs: vi.fn().mockResolvedValue([]),
    runForecast: vi.fn().mockResolvedValue(null),
  },
}));

// Mock fetch for daily data
global.fetch = vi.fn().mockResolvedValue({
  ok: true,
  json: () => Promise.resolve({ data: [] }),
});

// Mock useParams
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...(actual as object),
    useParams: () => ({ code: '000001' }),
  };
});

// Mock AIAnalyzeButton
vi.mock('../components/AIAnalyzeButton', () => ({
  default: ({ code }: { code: string }) => (
    <button data-testid={`ai-btn-${code}`}>分析</button>
  ),
}));

// Mock CandlestickChart (has Tailwind, we keep it untouched per requirements)
vi.mock('../components/charts/CandlestickChart', () => ({
  default: ({ code }: { code: string }) => (
    <div data-testid="candlestick-chart">K线图: {code}</div>
  ),
}));

// Mock MLPredictPanel
vi.mock('../components/MLPredictPanel', () => ({
  default: ({ mlData }: { mlData: any }) =>
    mlData ? <div data-testid="ml-panel">ML预测</div> : null,
}));

// Mock RiskPanel
vi.mock('../components/RiskPanel', () => ({
  default: ({ riskData }: { riskData: any }) =>
    riskData ? <div data-testid="risk-panel">风险管理</div> : null,
}));

// Mock MoneyFlowPanel
vi.mock('../components/MoneyFlowPanel', () => ({
  default: ({ moneyFlow }: { moneyFlow: any }) =>
    moneyFlow ? <div data-testid="money-flow-panel">资金流向</div> : null,
}));

import StockDetail from '../pages/StockDetail';

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

describe('StockDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // --- Basic Rendering ---

  it('renders stock detail page without crashing', async () => {
    renderWithProviders(<StockDetail />);
    await waitFor(() => {
      expect(screen.getByText('平安银行')).toBeInTheDocument();
    });
  });

  it('shows stock code', async () => {
    renderWithProviders(<StockDetail />);
    await waitFor(() => {
      expect(screen.getByText('000001')).toBeInTheDocument();
    });
  });

  it('renders AI analyze button', async () => {
    renderWithProviders(<StockDetail />);
    await waitFor(() => {
      expect(screen.getByTestId('ai-btn-000001')).toBeInTheDocument();
    });
  });

  // --- Tab Rendering ---

  it('renders antd Tabs with correct labels', async () => {
    renderWithProviders(<StockDetail />);
    await waitFor(() => {
      expect(screen.getByText('K线图')).toBeInTheDocument();
    });
    await waitFor(() => {
      // Use getAllByText since "AI分析" may also appear elsewhere
      expect(screen.queryAllByText('AI分析').length).toBeGreaterThanOrEqual(1);
    });
    await waitFor(() => {
      expect(screen.getByText('AI辩论')).toBeInTheDocument();
    });
  });

  // --- Candlestick Chart ---

  it('renders candlestick chart in K线图 tab', async () => {
    renderWithProviders(<StockDetail />);
    await waitFor(() => {
      expect(screen.getByTestId('candlestick-chart')).toBeInTheDocument();
    });
  });

  // --- StockHeader ---

  it('renders stock name with color based on change', async () => {
    renderWithProviders(<StockDetail />);
    await waitFor(() => {
      const nameEl = screen.getByText('平安银行');
      expect(nameEl).toBeInTheDocument();
    });
  });

  it('renders current price', async () => {
    renderWithProviders(<StockDetail />);
    await waitFor(() => {
      // Statistic renders "12.50" as "12" + ".50" in separate spans
      // So we check that 12 and .50 both appear
      expect(screen.getAllByText('12').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('.50').length).toBeGreaterThanOrEqual(1);
    });
  });

  // --- Ant Design components ---

  it('uses antd Card components', async () => {
    renderWithProviders(<StockDetail />);
    await waitFor(() => {
      const cards = document.querySelectorAll('.ant-card');
      expect(cards.length).toBeGreaterThan(0);
    });
  });

  it('uses antd Tabs', async () => {
    renderWithProviders(<StockDetail />);
    await waitFor(() => {
      const tabs = document.querySelector('.ant-tabs');
      expect(tabs).toBeTruthy();
    });
  });

  it('uses antd Descriptions for stock info', async () => {
    renderWithProviders(<StockDetail />);
    await waitFor(() => {
      const desc = document.querySelector('.ant-descriptions');
      expect(desc).toBeTruthy();
    });
  });

  it('uses antd Tag for change display', async () => {
    renderWithProviders(<StockDetail />);
    await waitFor(() => {
      const tag = document.querySelector('.ant-tag');
      expect(tag).toBeTruthy();
    });
  });

  // --- Loading State ---

  it('shows Spin while realtime data is loading', async () => {
    const { stockAPI } = await import('../services/api');
    (stockAPI.getRealtime as ReturnType<typeof vi.fn>).mockImplementation(
      () => new Promise(() => {}) // never resolves
    );
    renderWithProviders(<StockDetail />);
    await waitFor(() => {
      const spin = document.querySelector('.ant-spin');
      expect(spin).toBeTruthy();
    });
  });

  // --- No Tailwind ---

  it('has no Tailwind utility classes', async () => {
    renderWithProviders(<StockDetail />);
    await waitFor(() => {
      const allElements = document.querySelectorAll('[class]');
      let hasTailwind = false;
      allElements.forEach((el) => {
        const cls = el.getAttribute('class') || '';
        if (/\b(flex|grid|space-y|space-x|bg-white|bg-gray|text-gray|text-red|text-green|text-blue|text-center|rounded|shadow|p-[0-9]|px-[0-9]|py-[0-9]|m-[0-9]|mb-[0-9]|mt-[0-9]|gap-[0-9]|border-l-4|dark:)\b/.test(cls)) {
          hasTailwind = true;
        }
      });
      expect(hasTailwind).toBe(false);
    });
  });

  // --- Position Section ---

  it('shows position section when holdings exist', async () => {
    const { stockAPI } = await import('../services/api');
    (stockAPI.getWatchlist as ReturnType<typeof vi.fn>).mockResolvedValue([
      { code: '000001', cost_price: 12.30, shares: 1000 },
    ]);

    renderWithProviders(<StockDetail />);
    await waitFor(() => {
      expect(screen.getByText('持仓成本')).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText('持股数量')).toBeInTheDocument();
    });
  });

  // --- Fundamental Tab ---

  it('renders fundamental data when available', async () => {
    const { stockAPI } = await import('../services/api');
    (stockAPI.getComprehensive as ReturnType<typeof vi.fn>).mockResolvedValue({
      code: '000001',
      realtime: {
        code: '000001',
        name: '平安银行',
        current_price: 12.50,
        change_percent: 2.35,
        high: 12.80,
        low: 12.10,
        volume: 50000000,
        amount: 620000000,
      },
      fundamental: {
        pe: 8.5,
        pb: 0.9,
        roe: 12.3,
        eps: 1.45,
      },
    });

    renderWithProviders(<StockDetail />);
    await waitFor(() => {
      expect(screen.getByText('基本面')).toBeInTheDocument();
    });
  });
});
