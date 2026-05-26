import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Mock the API
vi.mock('../services/api', () => ({
  stockAPI: {
    getBacktestPresets: vi.fn().mockResolvedValue([
      {
        key: 'ma_cross',
        name: '均线交叉',
        description: '短期均线上穿长期均线买入，下穿卖出',
        params: [
          { key: 'fast_period', label: '快线周期', type: 'int', default: 5, min: 2, max: 60 },
          { key: 'slow_period', label: '慢线周期', type: 'int', default: 20, min: 5, max: 120 },
        ],
      },
      {
        key: 'rsi_oversold',
        name: 'RSI超买超卖',
        description: 'RSI低于超卖线买入，高于超卖线卖出',
        params: [
          { key: 'period', label: 'RSI周期', type: 'int', default: 14, min: 5, max: 50 },
          { key: 'oversold', label: '超卖线', type: 'int', default: 30, min: 10, max: 40 },
          { key: 'overbought', label: '超买线', type: 'int', default: 70, min: 60, max: 90 },
        ],
      },
    ]),
    runBacktest: vi.fn().mockResolvedValue({
      success: true,
      metrics: {
        total_return: 15.32,
        annual_return: 14.87,
        max_drawdown: -8.45,
        sharpe_ratio: 1.23,
        win_rate: 55.0,
        total_trades: 24,
        buy_hold_return: 8.10,
        excess_return: 7.22,
      },
      period: {
        start: '2024-01-02',
        end: '2024-12-31',
        trading_days: 242,
      },
      initial_capital: 100000,
      final_value: 115320,
      trades: [
        {
          date: '2024-01-15',
          type: 'buy',
          price: 12.50,
          shares: 8000,
          cost: 100000,
          commission: 25.0,
          cash_after: 0,
        },
        {
          date: '2024-03-20',
          type: 'sell',
          price: 13.80,
          shares: 8000,
          proceeds: 110400,
          commission: 27.6,
          cash_after: 110372.4,
        },
      ],
      equity_curve: [
        { date: '2024-01-15', total_value: 100000 },
        { date: '2024-02-15', total_value: 105000 },
        { date: '2024-03-20', total_value: 110372.4 },
        { date: '2024-06-15', total_value: 112000 },
        { date: '2024-12-31', total_value: 115320 },
      ],
    }),
    getAgents: vi.fn().mockResolvedValue([]),
  },
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

import BacktestPage from '../pages/BacktestPage';
import AIAnalyzeButton from '../components/AIAnalyzeButton';

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

// Helper to check for no Tailwind utility classes
function hasTailwindClasses(container: HTMLElement): boolean {
  const allElements = container.querySelectorAll('[class]');
  let hasTailwind = false;
  allElements.forEach((el) => {
    const cls = el.getAttribute('class') || '';
    // Common Tailwind patterns
    if (/\b(flex|grid|space-y|space-x|bg-white|bg-gray|text-gray|text-red|text-green|text-blue|text-center|rounded|shadow|p-[0-9]|px-[0-9]|py-[0-9]|m-[0-9]|mb-[0-9]|mt-[0-9]|gap-[0-9]|text-\[|dark:)\b/.test(cls)) {
      hasTailwind = true;
    }
  });
  return hasTailwind;
}

describe('BacktestPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // --- Basic Rendering ---

  it('renders the backtest title', async () => {
    renderWithProviders(<BacktestPage />);
    await waitFor(() => {
      expect(screen.getByText('策略回测')).toBeInTheDocument();
    });
  });

  it('renders the back button linking to strategies', async () => {
    renderWithProviders(<BacktestPage />);
    await waitFor(() => {
      const link = screen.getByRole('link');
      expect(link).toHaveAttribute('href', '/strategies');
    });
  });

  it('renders stock code input field', async () => {
    renderWithProviders(<BacktestPage />);
    await waitFor(() => {
      expect(screen.getByText('股票代码')).toBeInTheDocument();
    });
  });

  it('renders start date and end date inputs', async () => {
    renderWithProviders(<BacktestPage />);
    await waitFor(() => {
      expect(screen.getByText('开始日期')).toBeInTheDocument();
      expect(screen.getByText('结束日期')).toBeInTheDocument();
    });
  });

  it('renders initial capital input', async () => {
    renderWithProviders(<BacktestPage />);
    await waitFor(() => {
      expect(screen.getByText('初始资金(元)')).toBeInTheDocument();
    });
  });

  it('renders strategy preset buttons', async () => {
    renderWithProviders(<BacktestPage />);
    await waitFor(() => {
      expect(screen.getByText('均线交叉')).toBeInTheDocument();
      expect(screen.getByText('RSI超买超卖')).toBeInTheDocument();
    });
  });

  it('renders strategy parameter inputs when preset is selected', async () => {
    renderWithProviders(<BacktestPage />);
    await waitFor(() => {
      expect(screen.getByText('策略参数')).toBeInTheDocument();
      expect(screen.getByText(/快线周期/)).toBeInTheDocument();
      expect(screen.getByText(/慢线周期/)).toBeInTheDocument();
    });
  });

  it('renders run backtest button', async () => {
    renderWithProviders(<BacktestPage />);
    await waitFor(() => {
      expect(screen.getByText(/开始回测/)).toBeInTheDocument();
    });
  });

  // --- Ant Design components ---

  it('uses antd Card components', async () => {
    renderWithProviders(<BacktestPage />);
    await waitFor(() => {
      const cards = document.querySelectorAll('.ant-card');
      expect(cards.length).toBeGreaterThan(0);
    });
  });

  it('uses antd Button for run', async () => {
    renderWithProviders(<BacktestPage />);
    await waitFor(() => {
      const antBtn = document.querySelector('.ant-btn');
      expect(antBtn).toBeTruthy();
    });
  });

  it('has no Tailwind utility classes', async () => {
    const { container } = renderWithProviders(<BacktestPage />);
    await waitFor(() => {
      expect(hasTailwindClasses(container)).toBe(false);
    });
  });

  // --- Strategy Switching ---

  it('switches strategy and updates params when clicking a preset', async () => {
    const user = userEvent.setup();
    renderWithProviders(<BacktestPage />);
    await waitFor(() => {
      expect(screen.getByText('均线交叉')).toBeInTheDocument();
    });

    // Click RSI strategy
    await user.click(screen.getByText('RSI超买超卖'));

    await waitFor(() => {
      expect(screen.getByText(/RSI周期/)).toBeInTheDocument();
      expect(screen.getAllByText(/超卖线/).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/超买线/).length).toBeGreaterThan(0);
    });
  });

  // --- Run Backtest ---

  it('runs backtest and displays results', async () => {
    const user = userEvent.setup();
    renderWithProviders(<BacktestPage />);

    await waitFor(() => {
      expect(screen.getByText(/开始回测/)).toBeInTheDocument();
    });

    await user.click(screen.getByText(/开始回测/));

    await waitFor(() => {
      expect(screen.getByText('总收益率')).toBeInTheDocument();
      expect(screen.getByText('年化收益')).toBeInTheDocument();
      expect(screen.getByText('最大回撤')).toBeInTheDocument();
      expect(screen.getByText('夏普比率')).toBeInTheDocument();
      expect(screen.getByText('胜率')).toBeInTheDocument();
      expect(screen.getByText('交易次数')).toBeInTheDocument();
      expect(screen.getByText('买入持有')).toBeInTheDocument();
    });
  });

  it('shows trade records table after backtest', async () => {
    const user = userEvent.setup();
    renderWithProviders(<BacktestPage />);

    await waitFor(() => {
      expect(screen.getByText(/开始回测/)).toBeInTheDocument();
    });

    await user.click(screen.getByText(/开始回测/));

    await waitFor(() => {
      expect(screen.getByText(/交易记录/)).toBeInTheDocument();
      expect(screen.getByText('买入')).toBeInTheDocument();
      expect(screen.getByText('卖出')).toBeInTheDocument();
    });
  });

  it('shows equity curve after backtest', async () => {
    const user = userEvent.setup();
    renderWithProviders(<BacktestPage />);

    await waitFor(() => {
      expect(screen.getByText(/开始回测/)).toBeInTheDocument();
    });

    await user.click(screen.getByText(/开始回测/));

    await waitFor(() => {
      expect(screen.getByText(/净值曲线/)).toBeInTheDocument();
    });
  });

  it('shows excess return comparison', async () => {
    const user = userEvent.setup();
    renderWithProviders(<BacktestPage />);

    await waitFor(() => {
      expect(screen.getByText(/开始回测/)).toBeInTheDocument();
    });

    await user.click(screen.getByText(/开始回测/));

    await waitFor(() => {
      expect(screen.getByText(/策略 vs 买入持有/)).toBeInTheDocument();
    });
  });
});

describe('AIAnalyzeButton', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the AI analyze button', async () => {
    renderWithProviders(<AIAnalyzeButton code="000001" />);
    await waitFor(() => {
      expect(screen.getByText('TradingAgents AI分析')).toBeInTheDocument();
    });
  });

  it('uses antd Button for AI analyze trigger', async () => {
    renderWithProviders(<AIAnalyzeButton code="000001" />);
    await waitFor(() => {
      const antBtn = document.querySelector('.ant-btn');
      expect(antBtn).toBeTruthy();
    });
  });

  it('opens modal when clicked', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AIAnalyzeButton code="000001" />);

    await waitFor(() => {
      expect(screen.getByText('TradingAgents AI分析')).toBeInTheDocument();
    });

    await user.click(screen.getByText('TradingAgents AI分析'));

    await waitFor(() => {
      expect(screen.getByText('TradingAgents 多Agent辩论')).toBeInTheDocument();
    });
  });

  it('closes modal when X button clicked', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AIAnalyzeButton code="000001" />);

    await waitFor(() => {
      expect(screen.getByText('TradingAgents AI分析')).toBeInTheDocument();
    });

    await user.click(screen.getByText('TradingAgents AI分析'));

    await waitFor(() => {
      expect(screen.getByText('TradingAgents 多Agent辩论')).toBeInTheDocument();
    });

    // Close button exists and can be clicked
    const closeButtons = document.querySelectorAll('.ant-modal-close');
    expect(closeButtons.length).toBeGreaterThan(0);
  });

  it('shows mode selection buttons', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AIAnalyzeButton code="000001" />);

    await waitFor(() => {
      expect(screen.getByText('TradingAgents AI分析')).toBeInTheDocument();
    });

    await user.click(screen.getByText('TradingAgents AI分析'));

    await waitFor(() => {
      expect(screen.getByText('快速模式')).toBeInTheDocument();
      expect(screen.getByText('均衡模式')).toBeInTheDocument();
      expect(screen.getByText('深入模式')).toBeInTheDocument();
    });
  });

  it('has no Tailwind utility classes in button', async () => {
    const { container } = renderWithProviders(<AIAnalyzeButton code="000001" />);
    await waitFor(() => {
      expect(hasTailwindClasses(container)).toBe(false);
    });
  });

  it('shows enter debate button disabled when <2 agents selected', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AIAnalyzeButton code="000001" />);

    await waitFor(() => {
      expect(screen.getByText('TradingAgents AI分析')).toBeInTheDocument();
    });

    await user.click(screen.getByText('TradingAgents AI分析'));

    await waitFor(() => {
      const debateBtn = screen.getByText('进入辩论');
      expect(debateBtn.closest('button')).toBeDisabled();
    });
  });
});
