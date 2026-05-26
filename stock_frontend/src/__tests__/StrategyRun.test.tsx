import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Mock the API
const mockGetStrategyDetail = vi.fn();
const mockGetWatchlist = vi.fn();
const mockListSectors = vi.fn();
const mockGetSectorStocks = vi.fn();
const mockRunStrategy = vi.fn();
const mockApplyStrategy = vi.fn();
const mockGetDebateJobStatus = vi.fn();

vi.mock('../services/api', () => ({
  stockAPI: {
    getStrategyDetail: (...args: any[]) => mockGetStrategyDetail(...args),
    getWatchlist: (...args: any[]) => mockGetWatchlist(...args),
    listSectors: (...args: any[]) => mockListSectors(...args),
    getSectorStocks: (...args: any[]) => mockGetSectorStocks(...args),
    runStrategy: (...args: any[]) => mockRunStrategy(...args),
    applyStrategy: (...args: any[]) => mockApplyStrategy(...args),
    getDebateJobStatus: (...args: any[]) => mockGetDebateJobStatus(...args),
  },
}));

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...(actual as object),
    useNavigate: () => mockNavigate,
    useParams: () => ({ id: '1' }),
  };
});

// Mock ApplyToPaperPanel
vi.mock('../components/ApplyToPaperPanel', () => ({
  default: () => <div data-testid="apply-to-paper-panel">ApplyToPaperPanel</div>,
}));

// Mock marked and DOMPurify
vi.mock('marked', () => ({
  marked: { parse: vi.fn(() => '<p>Mocked markdown</p>') },
}));

vi.mock('dompurify', () => ({
  default: { sanitize: vi.fn((s: string) => s) },
}));

import StrategyRun from '../pages/StrategyRun';

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

describe('StrategyRun', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetStrategyDetail.mockResolvedValue({
      id: 1,
      name: '测试策略',
      description: '这是一个测试策略描述',
      category: 'youzi',
      enabled: true,
      sort_order: 1,
      created_at: '2025-01-01',
      agent_count: 2,
      doc_md: '',
      agent_configs: [
        { name: 'Agent A', type: 'default', sort_order: 1, prompt: '分析股票' },
        { name: 'Agent B', type: 'intraday_t', sort_order: 2, prompt: '打板分析' },
      ],
    });
    mockGetWatchlist.mockResolvedValue([]);
    mockListSectors.mockResolvedValue([]);
    mockApplyStrategy.mockResolvedValue({ message: '应用成功', count: 2, results: [] });
  });

  // --- Basic Rendering ---

  it('renders strategy name after loading', async () => {
    renderWithProviders(<StrategyRun />);
    await waitFor(() => {
      expect(screen.getByText('测试策略')).toBeInTheDocument();
    });
  });

  it('renders agent count badge', async () => {
    renderWithProviders(<StrategyRun />);
    await waitFor(() => {
      expect(screen.getByText('2个Agent')).toBeInTheDocument();
    });
  });

  it('renders mode selection buttons', async () => {
    renderWithProviders(<StrategyRun />);
    await waitFor(() => {
      expect(screen.getByText('快速模式')).toBeInTheDocument();
      expect(screen.getByText('均衡模式')).toBeInTheDocument();
      expect(screen.getByText('深入模式')).toBeInTheDocument();
    });
  });

  it('renders stock selection section', async () => {
    renderWithProviders(<StrategyRun />);
    await waitFor(() => {
      expect(screen.getByText('选择股票')).toBeInTheDocument();
    });
  });

  it('renders agent list section', async () => {
    renderWithProviders(<StrategyRun />);
    await waitFor(() => {
      expect(screen.getByText(/参与Agent/)).toBeInTheDocument();
    });
  });

  // --- Loading State ---

  it('shows loading state initially', () => {
    mockGetStrategyDetail.mockReturnValue(new Promise(() => {}));
    renderWithProviders(<StrategyRun />);
    expect(screen.getByText('加载策略...')).toBeInTheDocument();
  });

  // --- Ant Design Components ---

  it('uses antd components', async () => {
    renderWithProviders(<StrategyRun />);
    await waitFor(() => {
      const antElements = document.querySelectorAll('[class*="ant-"]');
      expect(antElements.length).toBeGreaterThan(0);
    });
  });

  it('has no Tailwind utility classes', async () => {
    renderWithProviders(<StrategyRun />);
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

  // --- Start button ---

  it('shows start button', async () => {
    renderWithProviders(<StrategyRun />);
    await waitFor(() => {
      expect(screen.getByText(/启动.*分析/)).toBeInTheDocument();
    });
  });

  // --- Manual code input ---

  it('renders manual code input', async () => {
    renderWithProviders(<StrategyRun />);
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/股票代码/)).toBeInTheDocument();
    });
  });

  // --- Watchlist area ---

  it('renders watchlist section', async () => {
    renderWithProviders(<StrategyRun />);
    await waitFor(() => {
      expect(screen.getByText('自选股')).toBeInTheDocument();
    });
  });
});
