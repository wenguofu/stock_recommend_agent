import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Watchlist from '../pages/Watchlist';

// Mock the store
const mockFetchWatchlist = vi.fn();
const mockAddStock = vi.fn();
const mockRemoveStock = vi.fn();

vi.mock('../store/watchlistStore', () => ({
  useWatchlistStore: vi.fn(),
}));

// Mock the API
vi.mock('../services/api', () => ({
  stockAPI: {
    getRealtime: vi.fn(),
    getAgents: vi.fn(),
    startMultiSelectDebate: vi.fn(),
    updateWatchlistPosition: vi.fn(),
  },
}));

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

import { useWatchlistStore } from '../store/watchlistStore';

const mockUseWatchlistStore = useWatchlistStore as ReturnType<typeof vi.fn>;

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

describe('Watchlist', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseWatchlistStore.mockReturnValue({
      items: [],
      loading: false,
      error: null,
      fetchWatchlist: mockFetchWatchlist,
      addStock: mockAddStock,
      removeStock: mockRemoveStock,
    });
  });

  // --- Basic Rendering ---

  it('renders the page title', () => {
    renderWithProviders(<Watchlist />);
    expect(screen.getByText('自选股管理')).toBeInTheDocument();
  });

  it('renders the add-form section', () => {
    renderWithProviders(<Watchlist />);
    expect(screen.getByText('添加自选股')).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/股票代码/)).toBeInTheDocument();
    // antd Button renders "添 加" with a space between CJK chars
    const addBtn = screen.getByRole('button', { name: '添 加' });
    expect(addBtn).toBeInTheDocument();
  });

  it('renders the watchlist section header', () => {
    renderWithProviders(<Watchlist />);
    expect(screen.getByText('我的自选')).toBeInTheDocument();
  });

  // --- Empty State ---

  it('shows empty state when no items and not loading', () => {
    mockUseWatchlistStore.mockReturnValue({
      items: [],
      loading: false,
      error: null,
      fetchWatchlist: mockFetchWatchlist,
      addStock: mockAddStock,
      removeStock: mockRemoveStock,
    });
    renderWithProviders(<Watchlist />);
    expect(screen.getByText('暂无自选股')).toBeInTheDocument();
  });

  // --- Loading State ---

  it('shows loading indicator when loading', () => {
    mockUseWatchlistStore.mockReturnValue({
      items: [],
      loading: true,
      error: null,
      fetchWatchlist: mockFetchWatchlist,
      addStock: mockAddStock,
      removeStock: mockRemoveStock,
    });
    renderWithProviders(<Watchlist />);
    // Should show a Spin component
    const loadingElem = document.querySelector('.ant-spin');
    expect(loadingElem).toBeTruthy();
    // With loading=true, the spin should be active
    const spinContainer = document.querySelector('.ant-spin-spinning');
    expect(spinContainer).toBeTruthy();
  });

  // --- Items Render ---

  it('renders watchlist items in the table', () => {
    mockUseWatchlistStore.mockReturnValue({
      items: [
        { id: 1, code: '000001', name: '平安银行', sort_order: 0 },
        { id: 2, code: '600519', name: '贵州茅台', sort_order: 1, cost_price: 1800, shares: 100 },
      ],
      loading: false,
      error: null,
      fetchWatchlist: mockFetchWatchlist,
      addStock: mockAddStock,
      removeStock: mockRemoveStock,
    });
    renderWithProviders(<Watchlist />);
    expect(screen.getByText('平安银行')).toBeInTheDocument();
    expect(screen.getByText('000001')).toBeInTheDocument();
    expect(screen.getByText('贵州茅台')).toBeInTheDocument();
    expect(screen.getByText('600519')).toBeInTheDocument();
  });

  // --- Error State ---

  it('shows error alert when store has error', () => {
    mockUseWatchlistStore.mockReturnValue({
      items: [],
      loading: false,
      error: 'Failed to fetch watchlist',
      fetchWatchlist: mockFetchWatchlist,
      addStock: mockAddStock,
      removeStock: mockRemoveStock,
    });
    renderWithProviders(<Watchlist />);
    expect(screen.getByText(/Failed to fetch watchlist/)).toBeInTheDocument();
  });

  // --- Checkbox toggle shows position fields ---

  it('shows position input fields when checkbox is checked', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Watchlist />);

    const checkbox = screen.getByText('添加持仓信息');
    await user.click(checkbox);

    expect(screen.getByPlaceholderText('持仓成本价（元）')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('持股数量（股）')).toBeInTheDocument();
  });

  // --- Multi-select button hidden when < 2 selected ---

  it('does not show multi-select button when less than 2 items are selected', () => {
    mockUseWatchlistStore.mockReturnValue({
      items: [
        { id: 1, code: '000001', name: '平安银行', sort_order: 0 },
      ],
      loading: false,
      error: null,
      fetchWatchlist: mockFetchWatchlist,
      addStock: mockAddStock,
      removeStock: mockRemoveStock,
    });
    renderWithProviders(<Watchlist />);
    expect(screen.queryByText('多选一 AI分析')).not.toBeInTheDocument();
  });

  // --- Add form: shows adding state ---

  it('has add button enabled initially', async () => {
    renderWithProviders(<Watchlist />);
    // The button should be present and enabled
    const addBtn = screen.getByRole('button', { name: '添 加' });
    expect(addBtn).toBeInTheDocument();
    expect(addBtn).not.toBeDisabled();
  });
});
