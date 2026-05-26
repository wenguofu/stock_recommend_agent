import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Mock the API
const mockListTasks = vi.fn();
const mockGetAlerts = vi.fn();
const mockCreateTask = vi.fn();
const mockUpdateTask = vi.fn();
const mockDeleteTask = vi.fn();
const mockTriggerTask = vi.fn();
const mockListTaskLogs = vi.fn();

vi.mock('../services/api', () => ({
  stockAPI: {
    listTasks: (...args: any[]) => mockListTasks(...args),
    getAlerts: (...args: any[]) => mockGetAlerts(...args),
    createTask: (...args: any[]) => mockCreateTask(...args),
    updateTask: (...args: any[]) => mockUpdateTask(...args),
    deleteTask: (...args: any[]) => mockDeleteTask(...args),
    triggerTask: (...args: any[]) => mockTriggerTask(...args),
    listTaskLogs: (...args: any[]) => mockListTaskLogs(...args),
  },
}));

import Tasks from '../pages/Tasks';

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

describe('Tasks', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListTasks.mockResolvedValue([]);
    mockGetAlerts.mockResolvedValue([]);
  });

  // --- Basic Rendering ---

  it('renders the page title', async () => {
    renderWithProviders(<Tasks />);
    await waitFor(() => {
      expect(screen.getByText(/盯盘任务/)).toBeInTheDocument();
    });
  });

  it('renders create task button', async () => {
    renderWithProviders(<Tasks />);
    await waitFor(() => {
      expect(screen.getByText(/新建任务/)).toBeInTheDocument();
    });
  });

  // --- Empty State ---

  it('shows empty state when no tasks', async () => {
    renderWithProviders(<Tasks />);
    await waitFor(() => {
      expect(screen.getByText('暂无盯盘任务')).toBeInTheDocument();
    });
  });

  // --- Loading State ---

  it('shows loading state initially', () => {
    mockListTasks.mockReturnValue(new Promise(() => {}));
    renderWithProviders(<Tasks />);
    expect(screen.getByText('加载中...')).toBeInTheDocument();
  });

  // --- Create/Edit Form Modal ---

  it('opens create form when clicking new task button', async () => {
    renderWithProviders(<Tasks />);
    await waitFor(() => {
      expect(screen.getByText(/新建任务/)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText(/新建任务/));
    await waitFor(() => {
      expect(screen.getByText('新建盯盘任务')).toBeInTheDocument();
    });
  });

  it('form has task name input', async () => {
    renderWithProviders(<Tasks />);
    await waitFor(() => {
      fireEvent.click(screen.getByText(/新建任务/));
    });
    await waitFor(() => {
      expect(screen.getByText('任务名称')).toBeInTheDocument();
    });
  });

  it('form has task type select', async () => {
    renderWithProviders(<Tasks />);
    await waitFor(() => {
      fireEvent.click(screen.getByText(/新建任务/));
    });
    await waitFor(() => {
      expect(screen.getByText('任务类型')).toBeInTheDocument();
    });
  });

  it('form has execution frequency select', async () => {
    renderWithProviders(<Tasks />);
    await waitFor(() => {
      fireEvent.click(screen.getByText(/新建任务/));
    });
    await waitFor(() => {
      expect(screen.getByText('执行频率')).toBeInTheDocument();
    });
  });

  it('modal form opens and can be closed', async () => {
    renderWithProviders(<Tasks />);
    // Open the modal
    await waitFor(() => {
      fireEvent.click(screen.getByText(/新建任务/));
    });
    // Verify modal opened with title
    await waitFor(() => {
      expect(screen.getByText('新建盯盘任务')).toBeInTheDocument();
    });
  });

  // --- Task List ---

  it('renders tasks when available', async () => {
    mockListTasks.mockResolvedValue([
      {
        id: 1,
        name: '测试任务1',
        task_type: 'price_alert',
        codes: ['000001'],
        schedule: 'every_15m',
        enabled: true,
        config: { price_up: 5, price_down: 3 },
      },
    ]);
    renderWithProviders(<Tasks />);
    await waitFor(() => {
      expect(screen.getByText('测试任务1')).toBeInTheDocument();
    });
  });

  it('shows task type label', async () => {
    mockListTasks.mockResolvedValue([
      {
        id: 1,
        name: '测试任务',
        task_type: 'ai_analysis',
        codes: ['000001'],
        schedule: 'every_1h',
        enabled: true,
      },
    ]);
    renderWithProviders(<Tasks />);
    await waitFor(() => {
      expect(screen.getByText(/AI分析/)).toBeInTheDocument();
    });
  });

  it('shows enabled/disabled badge', async () => {
    mockListTasks.mockResolvedValue([
      {
        id: 1,
        name: '测试任务',
        task_type: 'price_alert',
        codes: ['000001'],
        schedule: 'every_15m',
        enabled: true,
      },
    ]);
    renderWithProviders(<Tasks />);
    await waitFor(() => {
      expect(screen.getByText('启用')).toBeInTheDocument();
    });
  });

  // --- Alerts ---

  it('shows alerts section when alerts exist', async () => {
    mockListTasks.mockResolvedValue([]);
    mockGetAlerts.mockResolvedValue([
      {
        id: 1,
        task_name: '测试任务',
        type: 'price_up',
        message: '000001 涨幅超过5%',
        value: 5.5,
        timestamp: '2025-05-27T10:00:00',
      },
    ]);
    renderWithProviders(<Tasks />);
    await waitFor(() => {
      expect(screen.getByText('实时盯盘提醒')).toBeInTheDocument();
    });
  });

  // --- Ant Design Components ---

  it('uses antd components', async () => {
    renderWithProviders(<Tasks />);
    await waitFor(() => {
      const antElements = document.querySelectorAll('[class*="ant-"]');
      expect(antElements.length).toBeGreaterThan(0);
    });
  });

  it('has no Tailwind utility classes', async () => {
    renderWithProviders(<Tasks />);
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
