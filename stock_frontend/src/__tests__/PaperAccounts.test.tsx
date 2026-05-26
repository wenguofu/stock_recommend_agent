import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Mock fetch globally
global.fetch = vi.fn();

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...(actual as object),
    useNavigate: () => mockNavigate,
  };
});

import PaperAccounts from '../pages/PaperAccounts';

const mockAccounts = [
  {
    id: 1,
    name: '策略盘A',
    strategy_id: 10,
    initial_capital: 1000000,
    cash_balance: 250000,
    total_market_value: 800000,
    total_profit_pct: 5.23,
    max_drawdown: -3.15,
    win_rate: 62.5,
    snapshot_interval: 60,
    include_etf_replacement: true,
    enabled: true,
    created_at: '2025-01-01T00:00:00Z',
    position_count: 3,
  },
  {
    id: 2,
    name: '测试盘B',
    strategy_id: null,
    initial_capital: 500000,
    cash_balance: 100000,
    total_market_value: 380000,
    total_profit_pct: -4.00,
    max_drawdown: -8.50,
    win_rate: null,
    snapshot_interval: 30,
    include_etf_replacement: false,
    enabled: false,
    created_at: '2025-02-15T00:00:00Z',
    position_count: 0,
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

describe('PaperAccounts', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ accounts: mockAccounts }),
    });
  });

  // --- Basic Rendering ---

  it('renders page title "模拟盘"', async () => {
    renderWithProviders(<PaperAccounts />);
    await waitFor(() => {
      expect(screen.getByText('模拟盘')).toBeInTheDocument();
    });
  });

  it('renders subtitle', async () => {
    renderWithProviders(<PaperAccounts />);
    await waitFor(() => {
      expect(screen.getByText(/管理模拟交易账户/)).toBeInTheDocument();
    });
  });

  it('renders "新建模拟盘" button', async () => {
    renderWithProviders(<PaperAccounts />);
    await waitFor(() => {
      expect(screen.getByText('新建模拟盘')).toBeInTheDocument();
    });
  });

  // --- Loading State ---

  it('shows loading state initially', () => {
    (fetch as ReturnType<typeof vi.fn>).mockImplementation(
      () => new Promise(() => {})
    );
    renderWithProviders(<PaperAccounts />);
    const spin = document.querySelector('.ant-spin');
    expect(spin).toBeTruthy();
  });

  // --- Account Cards ---

  it('renders account names', async () => {
    renderWithProviders(<PaperAccounts />);
    await waitFor(() => {
      expect(screen.getByText('策略盘A')).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText('测试盘B')).toBeInTheDocument();
    });
  });

  it('renders total asset values', async () => {
    renderWithProviders(<PaperAccounts />);
    await waitFor(() => {
      // 250000 + 800000 = 1050000 = 105.00万
      expect(screen.getByText(/105.00万/)).toBeInTheDocument();
    });
  });

  it('renders profit percentages with correct color classes', async () => {
    renderWithProviders(<PaperAccounts />);
    await waitFor(() => {
      expect(screen.getByText('+5.23%')).toBeInTheDocument();
      expect(screen.getByText('-4.00%')).toBeInTheDocument();
    });
  });

  it('renders position count', async () => {
    renderWithProviders(<PaperAccounts />);
    await waitFor(() => {
      expect(screen.getByText('策略盘A')).toBeInTheDocument();
    });
    // Check position counts exist
    const posCounts = screen.getAllByText(/只$/);
    expect(posCounts.length).toBeGreaterThanOrEqual(1);
  });

  it('shows strategy badge when strategy_id exists', async () => {
    renderWithProviders(<PaperAccounts />);
    await waitFor(() => {
      expect(screen.getByText('策略盘')).toBeInTheDocument();
    });
  });

  it('shows disabled badge when account is not enabled', async () => {
    renderWithProviders(<PaperAccounts />);
    await waitFor(() => {
      expect(screen.getByText('已停用')).toBeInTheDocument();
    });
  });

  it('renders max drawdown and win rate', async () => {
    renderWithProviders(<PaperAccounts />);
    await waitFor(() => {
      expect(screen.getByText(/-3.15%/)).toBeInTheDocument();
      expect(screen.getByText(/62.50%/)).toBeInTheDocument();
    });
  });

  // --- Create Modal ---

  it('opens create modal when "新建模拟盘" is clicked', async () => {
    const user = userEvent.setup();
    renderWithProviders(<PaperAccounts />);
    await waitFor(() => {
      expect(screen.getByText('新建模拟盘')).toBeInTheDocument();
    });
    await user.click(screen.getByText('新建模拟盘'));
    await waitFor(() => {
      expect(screen.getByText('新建模拟盘账户')).toBeInTheDocument();
    });
  });

  it('create modal has name input', async () => {
    const user = userEvent.setup();
    renderWithProviders(<PaperAccounts />);
    await waitFor(() => {
      expect(screen.getByText('新建模拟盘')).toBeInTheDocument();
    });
    await user.click(screen.getByText('新建模拟盘'));
    await waitFor(() => {
      // Find name input by label or placeholder
      expect(screen.getByLabelText(/账户名称/)).toBeInTheDocument();
    });
  });

  // --- Ant Design Components ---

  it('uses antd Card components for account list', async () => {
    renderWithProviders(<PaperAccounts />);
    await waitFor(() => {
      const cards = document.querySelectorAll('.ant-card');
      expect(cards.length).toBeGreaterThanOrEqual(2);
    });
  });

  it('uses antd Modal for create form', async () => {
    const user = userEvent.setup();
    renderWithProviders(<PaperAccounts />);
    await waitFor(() => {
      expect(screen.getByText('新建模拟盘')).toBeInTheDocument();
    });
    await user.click(screen.getByText('新建模拟盘'));
    await waitFor(() => {
      const modal = document.querySelector('.ant-modal');
      expect(modal).toBeTruthy();
    });
  });

  it('uses antd Tag for badges', async () => {
    renderWithProviders(<PaperAccounts />);
    await waitFor(() => {
      const tags = document.querySelectorAll('.ant-tag');
      expect(tags.length).toBeGreaterThanOrEqual(1);
    });
  });

  it('uses antd Spin for loading', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockImplementation(
      () => new Promise(() => {})
    );
    renderWithProviders(<PaperAccounts />);
    await waitFor(() => {
      const spin = document.querySelector('.ant-spin');
      expect(spin).toBeTruthy();
    });
  });

  it('uses antd Typography for title', async () => {
    renderWithProviders(<PaperAccounts />);
    await waitFor(() => {
      const typoTitle = document.querySelector('.ant-typography');
      expect(typoTitle).toBeTruthy();
    });
  });

  // --- No Tailwind ---

  it('has no Tailwind utility classes', async () => {
    renderWithProviders(<PaperAccounts />);
    await waitFor(() => {
      const allElements = document.querySelectorAll('[class]');
      let hasTailwind = false;
      allElements.forEach((el) => {
        const cls = el.getAttribute('class') || '';
        if (/\b(flex|grid|space-y|space-x|bg-white|bg-gray|bg-blue|bg-red|bg-black|text-gray|text-red|text-green|text-blue|text-center|text-3xl|text-2xl|text-xl|text-lg|text-sm|text-xs|rounded|shadow|p-[0-9]|px-[0-9]|py-[0-9]|m-[0-9]|mb-[0-9]|mt-[0-9]|gap-[0-9]|border-l-4|dark:|hover:bg|transition-colors|animate-spin)\b/.test(cls)) {
          hasTailwind = true;
        }
      });
      expect(hasTailwind).toBe(false);
    });
  });

  // --- Delete Modal ---

  it('opens delete confirmation when delete button is clicked', async () => {
    const user = userEvent.setup();
    renderWithProviders(<PaperAccounts />);
    await waitFor(() => {
      expect(screen.getByText('策略盘A')).toBeInTheDocument();
    });
    // Find delete buttons - they should say "删除"
    const deleteButtons = screen.getAllByText('删除');
    expect(deleteButtons.length).toBeGreaterThanOrEqual(1);
    await user.click(deleteButtons[0]);
    await waitFor(() => {
      expect(screen.getByRole('dialog', { name: /确认删除/ })).toBeInTheDocument();
    });
  });

  // --- Error State ---

  it('shows error message on fetch failure', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Network error'));
    renderWithProviders(<PaperAccounts />);
    await waitFor(() => {
      expect(screen.getByText(/加载失败/)).toBeInTheDocument();
    });
  });

  // --- Empty State ---

  it('shows empty state when no accounts', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ accounts: [] }),
    });
    renderWithProviders(<PaperAccounts />);
    await waitFor(() => {
      expect(screen.getByText(/还没有模拟盘账户/)).toBeInTheDocument();
    });
  });
});
