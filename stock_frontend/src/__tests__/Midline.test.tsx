import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Mock fetch globally
global.fetch = vi.fn();

import Midline from '../pages/Midline';

const mockHealth = {
  data: [
    { code: '000001', name: '平安银行', score: 85, ma_score: 40, macd_signal: '金叉', rsi_score: 30, trend: '上升', suggestion: '持有', shares: 1000, cost_price: 12.50 },
    { code: '600519', name: '贵州茅台', score: 55, ma_score: 25, macd_signal: '死叉', rsi_score: 20, trend: '震荡', suggestion: '观望', shares: null, cost_price: null },
  ],
};

const mockJournal = {
  data: [
    { id: 1, code: '000001', name: '平安银行', entry_date: '2025-01-15', entry_price: 12.50, shares: 1000, stop_loss: 11.50, exit_date: null, pnl: null, pnl_pct: null, reason_entry: 'MA金叉买入' },
    { id: 2, code: '600519', name: '贵州茅台', entry_date: '2025-02-01', entry_price: 1800.00, shares: 100, stop_loss: 1750.00, exit_date: '2025-03-01', pnl: 5000, pnl_pct: 2.78, reason_entry: '突破买入' },
  ],
};

const mockStats = {
  data: {
    total_trades: 2,
    win_rate: 50,
    wins: 1,
    losses: 1,
    total_pnl: 5000,
    profit_factor: 2.5,
    max_win_streak: 1,
    max_loss_streak: 1,
    avg_win: 5000,
    avg_loss: 0,
  },
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

describe('Midline', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    const mockFetch = fetch as ReturnType<typeof vi.fn>;
    mockFetch.mockImplementation((url: string) => {
      if (url.includes('watchlist-health')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(mockHealth) });
      }
      if (url.includes('journal/stats')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(mockStats) });
      }
      if (url.includes('journal') && !url.includes('stats')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(mockJournal) });
      }
      if (url.includes('position-calc')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            suggested_shares: 4000, position_value: 50000, position_pct: 50,
            max_loss_amount: 2000, risk_per_share: 0.5, risk_reward_ratio: 2.5,
          }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });
  });

  // --- Basic Rendering ---

  it('renders page title "中长线交易看板"', async () => {
    renderWithProviders(<Midline />);
    await waitFor(() => {
      expect(screen.getByText(/中长线交易看板/)).toBeInTheDocument();
    });
  });

  it('renders watchlist health section', async () => {
    renderWithProviders(<Midline />);
    await waitFor(() => {
      expect(screen.getByText(/自选池趋势健康度/)).toBeInTheDocument();
    });
  });

  it('renders position calculator section', async () => {
    renderWithProviders(<Midline />);
    await waitFor(() => {
      expect(screen.getByText(/仓位计算器/)).toBeInTheDocument();
    });
  });

  it('renders trade stats section', async () => {
    renderWithProviders(<Midline />);
    await waitFor(() => {
      expect(screen.getByText(/交易统计/)).toBeInTheDocument();
    });
  });

  it('renders trade journal section', async () => {
    renderWithProviders(<Midline />);
    await waitFor(() => {
      expect(screen.getByText(/交易日志/)).toBeInTheDocument();
    });
  });

  // --- Loading State ---

  it('shows loading state initially', () => {
    (fetch as ReturnType<typeof vi.fn>).mockImplementation(
      () => new Promise(() => {})
    );
    renderWithProviders(<Midline />);
    const spin = document.querySelector('.ant-spin');
    expect(spin).toBeTruthy();
  });

  // --- Data Rendering ---

  it('renders stock codes in health table', async () => {
    renderWithProviders(<Midline />);
    await waitFor(() => {
      expect(screen.getByText('000001')).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText('600519')).toBeInTheDocument();
    });
  });

  it('renders stock names in health table', async () => {
    renderWithProviders(<Midline />);
    await waitFor(() => {
      expect(screen.getByText('平安银行')).toBeInTheDocument();
      expect(screen.getByText('贵州茅台')).toBeInTheDocument();
    });
  });

  it('renders score with color classes', async () => {
    renderWithProviders(<Midline />);
    await waitFor(() => {
      expect(screen.getByText('85')).toBeInTheDocument();
      expect(screen.getByText('55')).toBeInTheDocument();
    });
  });

  it('renders position badge for stocks with shares', async () => {
    renderWithProviders(<Midline />);
    await waitFor(() => {
      expect(screen.getByText(/持仓 1000股/)).toBeInTheDocument();
    });
  });

  it('renders trade stats values', async () => {
    renderWithProviders(<Midline />);
    await waitFor(() => {
      // Statistic may render value and suffix separately; check for value
      const statValues = document.querySelectorAll('.ant-statistic-content-value');
      const hasWinRate = Array.from(statValues).some(el => el.textContent?.includes('50'));
      expect(hasWinRate).toBe(true);
    });
  });

  it('renders journal entries with code and name', async () => {
    renderWithProviders(<Midline />);
    await waitFor(() => {
      // The journal table shows codes
      const codeCells = screen.getAllByText(/000001/);
      expect(codeCells.length).toBeGreaterThanOrEqual(1);
    });
  });

  // --- Position Calculator ---

  it('has calculator input fields', async () => {
    renderWithProviders(<Midline />);
    await waitFor(() => {
      expect(screen.getByText(/仓位计算器/)).toBeInTheDocument();
    });
    // Should have input fields
    const inputs = document.querySelectorAll('input');
    expect(inputs.length).toBeGreaterThanOrEqual(3);
  });

  it('has a calculate button', async () => {
    renderWithProviders(<Midline />);
    await waitFor(() => {
      expect(screen.getByText(/计算仓位/)).toBeInTheDocument();
    });
  });

  // --- Ant Design Components ---

  it('uses antd Card components', async () => {
    renderWithProviders(<Midline />);
    await waitFor(() => {
      const cards = document.querySelectorAll('.ant-card');
      expect(cards.length).toBeGreaterThanOrEqual(3);
    });
  });

  it('uses antd Table for health data', async () => {
    renderWithProviders(<Midline />);
    await waitFor(() => {
      const tables = document.querySelectorAll('.ant-table');
      expect(tables.length).toBeGreaterThanOrEqual(1);
    });
  });

  it('uses antd Button for actions', async () => {
    renderWithProviders(<Midline />);
    await waitFor(() => {
      const buttons = document.querySelectorAll('.ant-btn');
      expect(buttons.length).toBeGreaterThanOrEqual(1);
    });
  });

  it('uses antd Spin for loading', () => {
    (fetch as ReturnType<typeof vi.fn>).mockImplementation(
      () => new Promise(() => {})
    );
    renderWithProviders(<Midline />);
    const spin = document.querySelector('.ant-spin');
    expect(spin).toBeTruthy();
  });

  // --- No Tailwind ---

  it('has no Tailwind utility classes', async () => {
    renderWithProviders(<Midline />);
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
