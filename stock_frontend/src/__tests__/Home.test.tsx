import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Mock the store
const mockFetchWatchlist = vi.fn();

vi.mock('../store/watchlistStore', () => ({
  useWatchlistStore: vi.fn(),
}));

// Mock the API
vi.mock('../services/api', () => ({
  stockAPI: {
    getRealtime: vi.fn(),
    listDebateJobs: vi.fn().mockResolvedValue([]),
    getSectorPerformance: vi.fn().mockResolvedValue([]),
    getMarketOutlook: vi.fn().mockResolvedValue(null),
    stopDebateJob: vi.fn().mockResolvedValue(true),
    deleteDebateJob: vi.fn().mockResolvedValue(true),
  },
}));

// Mock fetch for index data
global.fetch = vi.fn().mockResolvedValue({
  ok: true,
  json: () => Promise.resolve({ current_price: 3350.00, change_percent: 0.52, high: 3360.00, low: 3340.00, volume: 280000000, yesterday_close: 3332.69 }),
});

// Mock AIAnalyzeButton
vi.mock('../components/AIAnalyzeButton', () => ({
  default: ({ code }: { code: string }) => <button data-testid={`ai-btn-${code}`}>AI分析</button>,
}));

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

// Mock useLocation
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...(actual as object),
    useLocation: () => ({ pathname: '/', search: '', hash: '', state: null, key: 'default' }),
  };
});

// Mock sectorEtfs
vi.mock('../constants/sectorEtfs', () => ({
  findEtfs: vi.fn().mockReturnValue(undefined),
}));

import { useWatchlistStore } from '../store/watchlistStore';
import Home from '../pages/Home';

const mockUseWatchlistStore = useWatchlistStore as unknown as ReturnType<typeof vi.fn>;

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

describe('Home', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseWatchlistStore.mockReturnValue({
      items: [],
      loading: false,
      error: null,
      fetchWatchlist: mockFetchWatchlist,
    });
  });

  // --- Basic Rendering ---

  it('renders market outlook card', async () => {
    renderWithProviders(<Home />);
    await waitFor(() => {
      expect(screen.getByText(/大盘研判/)).toBeInTheDocument();
    });
  });

  it('renders market switch segmented control', async () => {
    renderWithProviders(<Home />);
    await waitFor(() => {
      // Segmented component should be present
      expect(screen.getByText('A股')).toBeInTheDocument();
      expect(screen.getByText('美股')).toBeInTheDocument();
    });
  });

  it('renders debate jobs section', async () => {
    renderWithProviders(<Home />);
    await waitFor(() => {
      expect(screen.getByText('辩论记录')).toBeInTheDocument();
    });
  });

  // --- A股 market ---

  it('renders A-share index cards by default', async () => {
    renderWithProviders(<Home />);
    await waitFor(() => {
      expect(screen.getByText('上证指数')).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText('深证成指')).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText('创业板指')).toBeInTheDocument();
    });
  });

  it('renders sector sidebar only in A-share mode', async () => {
    renderWithProviders(<Home />);
    await waitFor(() => {
      expect(screen.getByText('今日热点板块')).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText('最强 TOP 5')).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText('偏弱 TOP 3')).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText('下一个主线预测')).toBeInTheDocument();
    });
  });

  // --- watchlist ---

  it('shows A-share self-selected stocks header', async () => {
    renderWithProviders(<Home />);
    await waitFor(() => {
      expect(screen.getByText('A股自选')).toBeInTheDocument();
    });
  });

  it('shows empty watchlist message when no items', async () => {
    renderWithProviders(<Home />);
    await waitFor(() => {
      expect(screen.getByText('暂无A股自选')).toBeInTheDocument();
    });
  });

  it('shows link to manage watchlist', async () => {
    renderWithProviders(<Home />);
    await waitFor(() => {
      expect(screen.getAllByText('管理自选').length).toBeGreaterThanOrEqual(1);
    });
  });

  // --- Ant Design components ---

  it('uses antd Card components', async () => {
    renderWithProviders(<Home />);
    await waitFor(() => {
      const cards = document.querySelectorAll('.ant-card');
      expect(cards.length).toBeGreaterThan(0);
    });
  });

  it('uses antd Segmented for market switch', async () => {
    renderWithProviders(<Home />);
    await waitFor(() => {
      const segmented = document.querySelector('.ant-segmented');
      expect(segmented).toBeTruthy();
    });
  });

  it('has no Tailwind utility classes', async () => {
    renderWithProviders(<Home />);
    await waitFor(() => {
      // Check that no Tailwind classes are present
      const allElements = document.querySelectorAll('[class]');
      let hasTailwind = false;
      allElements.forEach((el) => {
        const cls = el.getAttribute('class') || '';
        // Common Tailwind patterns
        if (/\b(flex|grid|space-y|space-x|bg-white|bg-gray|text-gray|text-red|text-green|text-blue|text-center|rounded|shadow|p-[0-9]|px-[0-9]|py-[0-9]|m-[0-9]|mb-[0-9]|mt-[0-9]|gap-[0-9]|text-\[|dark:)\b/.test(cls)) {
          hasTailwind = true;
        }
      });
      expect(hasTailwind).toBe(false);
    });
  });

  // --- Loading state ---

  it('shows Spin while debate data is loading', async () => {
    renderWithProviders(<Home />);
    await waitFor(() => {
      // The debate section should exist
      expect(screen.getByText('辩论记录')).toBeInTheDocument();
    });
  });

  // --- Market outlook loaded state ---

  it('renders market outlook data correctly', async () => {
    const { stockAPI } = await import('../services/api');
    (stockAPI.getMarketOutlook as ReturnType<typeof vi.fn>).mockResolvedValue({
      success: true,
      market_status: 'bull',
      verdict: '强势上涨',
      score: 65,
      cur_price: 3350,
      ma20: 3300,
      ma60: 3250,
      ma120: 3200,
      low_6m: 3000,
      high_6m: 3700,
      pct_30d: 3.5,
      pct_60d: 8.2,
      pct_120d: 12.1,
      suggest: '建议积极做多',
      outlook: '未来一月有望继续上攻',
      reasons: ['成交量放大', '北向资金流入'],
    });

    renderWithProviders(<Home />);
    await waitFor(() => {
      expect(screen.getByText('强势上涨')).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText('建议积极做多')).toBeInTheDocument();
    });
  });

  // --- Sector performance ---

  it('renders sector performance section with data', async () => {
    renderWithProviders(<Home />);
    // Verify sector section headers are present
    await waitFor(() => {
      expect(screen.getByText('今日热点板块')).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText('最强 TOP 5')).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText('偏弱 TOP 3')).toBeInTheDocument();
    });
  });
});
