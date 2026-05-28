import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Mock react-router-dom
const mockSetSearchParams = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...(actual as object),
    useSearchParams: () => [new URLSearchParams('code=000001&job_id=test-job-123'), mockSetSearchParams],
    useLocation: () => ({
      pathname: '/ai-debate',
      search: '',
      hash: '',
      state: {
        code: '000001',
        agentIds: [1, 2],
        analysisRounds: 3,
        debateRounds: 3,
        modeLabel: '测试模式',
      },
      key: 'default',
    }),
  };
});

// Mock the API
vi.mock('../services/api', () => ({
  stockAPI: {
    getDebateJobStatus: vi.fn().mockResolvedValue({
      job_id: 'test-job-123',
      code: '000001',
      name: '平安银行',
      status: 'running',
      progress: 45,
      progress_detail: ['开始分析...', 'Bull Agent 正在分析第1轮...'],
      steps: [
        { phase: 'analysis', round: 1, agent_id: 1, agent_name: 'Bull Agent', content: '看多分析...', timestamp: '2025-01-01 10:00' },
        { phase: 'analysis', round: 1, agent_id: 2, agent_name: 'Bear Agent', content: '看空分析...', timestamp: '2025-01-01 10:05' },
      ],
      report_md: '# 分析报告\n测试报告',
      analysis_rounds: 3,
      debate_rounds: 3,
      agent_ids: [1, 2],
    }),
    getRealtime: vi.fn().mockResolvedValue({
      code: '000001',
      name: '平安银行',
      current_price: 12.50,
      change_percent: 2.35,
      volume: 150000000,
      amount: 1800000000,
      high: 12.80,
      low: 12.20,
      open: 12.30,
      yesterday_close: 12.21,
    }),
    getComprehensive: vi.fn().mockResolvedValue({
      code: '000001',
      realtime: {
        code: '000001', name: '平安银行', current_price: 12.50, change_percent: 2.35,
        volume: 150000000, amount: 1800000000, high: 12.80, low: 12.20,
        open: 12.30, yesterday_close: 12.21, turnover_rate: 1.5,
      },
      money_flow: { main_net_inflow: 5000, super_large_net_inflow: 3000 },
      fundamental: { pe: 8.5, pb: 1.2, ps: 1.8, roe: 12.5, eps: 1.5, bps: 12.0 },
      industry_comparison: { industry_name: '银行', rank: 3, avg_change_percent: 1.8, total: 42 },
    }),
    getSentiment: vi.fn().mockResolvedValue({
      news: { count: 25 },
      posts: { total_count: 150, latest_count: 30, hot_count: 12 },
    }),
    startDebateJob: vi.fn().mockResolvedValue({ job_id: 'test-job-123' }),
    stopDebateJob: vi.fn().mockResolvedValue(true),
    deleteDebateJob: vi.fn().mockResolvedValue(true),
  },
}));

// Mock antd App.useApp
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

import AIDebate from '../pages/AIDebate';

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/ai-debate?code=000001&job_id=test-job-123']}>
        {ui}
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('AIDebate', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // --- Basic Rendering ---

  it('renders debate page with stock name', async () => {
    renderWithProviders(<AIDebate />);
    await waitFor(() => {
      expect(screen.getByText(/TradingAgents 辩论分析/)).toBeInTheDocument();
    });
  });

  it('renders progress bar section', async () => {
    renderWithProviders(<AIDebate />);
    await waitFor(() => {
      expect(screen.getByText(/进度提示/)).toBeInTheDocument();
    });
  });

  it('renders thinking process section', async () => {
    renderWithProviders(<AIDebate />);
    await waitFor(() => {
      expect(screen.getByText('专家思考过程（可滚动）')).toBeInTheDocument();
    });
  });

  it('renders basic info section', async () => {
    renderWithProviders(<AIDebate />);
    await waitFor(() => {
      expect(screen.getByText('基础信息（接口数据）')).toBeInTheDocument();
    });
  });

  it('renders report section', async () => {
    renderWithProviders(<AIDebate />);
    await waitFor(() => {
      expect(screen.getByText('研究报告（Markdown）')).toBeInTheDocument();
    });
  });

  it('renders stop and delete buttons', async () => {
    renderWithProviders(<AIDebate />);
    await waitFor(() => {
      expect(screen.getByText('终止')).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText('删除')).toBeInTheDocument();
    });
  });

  // --- Ant Design components ---

  it('uses antd Card components', async () => {
    renderWithProviders(<AIDebate />);
    await waitFor(() => {
      const cards = document.querySelectorAll('.ant-card');
      expect(cards.length).toBeGreaterThan(0);
    });
  });

  it('uses antd Button components', async () => {
    renderWithProviders(<AIDebate />);
    await waitFor(() => {
      const buttons = document.querySelectorAll('.ant-btn');
      expect(buttons.length).toBeGreaterThan(0);
    });
  });

  it('uses antd Tag for status', async () => {
    renderWithProviders(<AIDebate />);
    await waitFor(() => {
      const tags = document.querySelectorAll('.ant-tag');
      expect(tags.length).toBeGreaterThan(0);
    });
  });

  it('uses antd Spin for loading', async () => {
    renderWithProviders(<AIDebate />);
    await waitFor(() => {
      const spin = document.querySelector('.ant-spin');
      expect(spin).toBeTruthy();
    });
  });

  // --- No Tailwind ---

  it('has no Tailwind utility classes', async () => {
    renderWithProviders(<AIDebate />);
    await waitFor(() => {
      const allElements = document.querySelectorAll('[class]');
      let hasTailwind = false;
      allElements.forEach((el) => {
        const cls = el.getAttribute('class') || '';
        if (/\b(flex|grid|space-y|space-x|bg-white|bg-gray|text-gray|text-red|text-green|text-blue|text-center|rounded|shadow|p-6|px-4|py-2|m-[0-9]|mb-4|mt-2|gap-2|dark:)\b/.test(cls)) {
          hasTailwind = true;
        }
      });
      expect(hasTailwind).toBe(false);
    });
  });

  // --- Data rendering ---

  it('renders agent names in thinking process', async () => {
    renderWithProviders(<AIDebate />);
    await waitFor(() => {
      expect(screen.getByText('Bull Agent')).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText('Bear Agent')).toBeInTheDocument();
    });
  });

  it('renders progress percentage', async () => {
    renderWithProviders(<AIDebate />);
    await waitFor(() => {
      const elements = screen.getAllByText('45%');
      expect(elements.length).toBeGreaterThanOrEqual(1);
    });
  });
});
