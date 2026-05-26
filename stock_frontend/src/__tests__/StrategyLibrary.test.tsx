import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Mock the API
const mockGetStrategies = vi.fn();
const mockGetStrategyDetail = vi.fn();
const mockApplyStrategy = vi.fn();

vi.mock('../services/api', () => ({
  stockAPI: {
    getStrategies: (...args: any[]) => mockGetStrategies(...args),
    getStrategyDetail: (...args: any[]) => mockGetStrategyDetail(...args),
    applyStrategy: (...args: any[]) => mockApplyStrategy(...args),
  },
}));

// Mock react-router-dom (keep MemoryRouter but mock navigate)
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...(actual as object),
    useNavigate: () => mockNavigate,
  };
});

import StrategyLibrary from '../pages/StrategyLibrary';

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

describe('StrategyLibrary', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetStrategies.mockResolvedValue({
      strategies: [
        { id: 1, name: '龙虎榜跟踪', description: '追踪龙虎榜游资动向', category: 'youzi', agent_count: 5, enabled: true, sort_order: 1, created_at: '2025-01-01' },
        { id: 2, name: '均线交叉', description: '金叉死叉信号', category: 'lianghua', agent_count: 3, enabled: true, sort_order: 2, created_at: '2025-01-02' },
      ],
      count: 2,
    });
    mockGetStrategyDetail.mockResolvedValue({
      id: 1,
      name: '龙虎榜跟踪',
      description: '追踪龙虎榜游资动向',
      category: 'youzi',
      agent_count: 5,
      enabled: true,
      sort_order: 1,
      created_at: '2025-01-01',
      doc_md: '# 策略说明\n\n这是测试文档',
      agent_configs: [
        { name: '打板Agent', type: 'intraday_t', sort_order: 1, prompt: '分析涨停板数据' },
        { name: '复盘Agent', type: 'review', sort_order: 2, prompt: '复盘当天操作' },
      ],
    });
    mockApplyStrategy.mockResolvedValue({ message: '应用成功', count: 2, results: [] });
  });

  // --- Basic Rendering ---

  it('renders the page title', async () => {
    renderWithProviders(<StrategyLibrary />);
    await waitFor(() => {
      expect(screen.getByText('策略库')).toBeInTheDocument();
    });
  });

  it('renders category filter buttons', async () => {
    renderWithProviders(<StrategyLibrary />);
    await waitFor(() => {
      expect(screen.getByText('全部策略')).toBeInTheDocument();
      expect(screen.getByText('游资策略')).toBeInTheDocument();
      expect(screen.getByText('基础工具')).toBeInTheDocument();
      expect(screen.getByText('量化策略')).toBeInTheDocument();
    });
  });

  it('renders strategy list after loading', async () => {
    renderWithProviders(<StrategyLibrary />);
    await waitFor(() => {
      expect(screen.getByText('龙虎榜跟踪')).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText('均线交叉')).toBeInTheDocument();
    });
  });

  it('shows agent count on cards', async () => {
    renderWithProviders(<StrategyLibrary />);
    await waitFor(() => {
      expect(screen.getByText('5个Agent')).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText('3个Agent')).toBeInTheDocument();
    });
  });

  it('shows empty placeholder when no strategy selected', async () => {
    renderWithProviders(<StrategyLibrary />);
    await waitFor(() => {
      expect(screen.getByText('选择一个策略')).toBeInTheDocument();
    });
  });

  // --- Loading state ---

  it('shows loading state', async () => {
    mockGetStrategies.mockReturnValue(new Promise(() => {})); // never resolves
    renderWithProviders(<StrategyLibrary />);
    await waitFor(() => {
      expect(screen.getByText('加载策略...')).toBeInTheDocument();
    });
  });

  // --- Error state ---

  it('shows error state', async () => {
    mockGetStrategies.mockRejectedValue(new Error('Network error'));
    renderWithProviders(<StrategyLibrary />);
    await waitFor(() => {
      expect(screen.getByText('加载失败')).toBeInTheDocument();
    });
  });

  // --- Selecting a strategy ---

  it('loads strategy detail on click', async () => {
    renderWithProviders(<StrategyLibrary />);
    await waitFor(() => {
      expect(screen.getByText('龙虎榜跟踪')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText('龙虎榜跟踪'));
    await waitFor(() => {
      expect(mockGetStrategyDetail).toHaveBeenCalledWith(1);
    });
    await waitFor(() => {
      expect(screen.getByText(/包含的Agent/)).toBeInTheDocument();
    });
  });

  // --- Strategy detail: agent list ---

  it('shows agent configs in detail', async () => {
    renderWithProviders(<StrategyLibrary />);
    await waitFor(() => {
      fireEvent.click(screen.getByText('龙虎榜跟踪'));
    });
    await waitFor(() => {
      expect(screen.getByText('打板Agent')).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText('复盘Agent')).toBeInTheDocument();
    });
  });

  // --- Apply strategy ---

  it('applies strategy and shows result', async () => {
    renderWithProviders(<StrategyLibrary />);
    await waitFor(() => {
      fireEvent.click(screen.getByText('龙虎榜跟踪'));
    });
    await waitFor(() => {
      expect(screen.getByText('应用配置')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText('应用配置'));
    await waitFor(() => {
      expect(mockApplyStrategy).toHaveBeenCalledWith(1);
    });
    await waitFor(() => {
      expect(screen.getByText(/策略应用成功/)).toBeInTheDocument();
    });
  });

  // --- Strategy doc ---

  it('shows strategy doc toggle', async () => {
    renderWithProviders(<StrategyLibrary />);
    await waitFor(() => {
      fireEvent.click(screen.getByText('龙虎榜跟踪'));
    });
    await waitFor(() => {
      expect(screen.getByText('策略说明文档')).toBeInTheDocument();
    });
  });

  // --- Ant Design components ---

  it('uses antd components', async () => {
    renderWithProviders(<StrategyLibrary />);
    await waitFor(() => {
      const antElements = document.querySelectorAll('[class*="ant-"]');
      expect(antElements.length).toBeGreaterThan(0);
    });
  });

  it('has no Tailwind utility classes', async () => {
    renderWithProviders(<StrategyLibrary />);
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
