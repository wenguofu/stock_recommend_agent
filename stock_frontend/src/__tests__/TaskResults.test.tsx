import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const mockSchedulerRuns = vi.fn();
const mockListTasks = vi.fn();
const mockTaskLogsByDate = vi.fn();

vi.mock('../services/api', () => ({
  stockAPI: {
    schedulerRuns: (...args: any[]) => mockSchedulerRuns(...args),
    listTasks: (...args: any[]) => mockListTasks(...args),
    taskLogsByDate: (...args: any[]) => mockTaskLogsByDate(...args),
  },
}));

import TaskResults from '../pages/TaskResults';

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

describe('TaskResults', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSchedulerRuns.mockResolvedValue({
      success: true,
      data: [
        {
          id: 1,
          task_name: '板块更新',
          task_type: 'cron',
          schedule: '0 9 * * 1-5',
          status: 'success',
          output: '已加载 12 个板块',
          error: '',
          started_at: '2026-06-16T09:00:12',
          finished_at: '2026-06-16T09:00:13',
          duration_ms: 1147,
          trigger_source: 'auto',
        },
        {
          id: 2,
          task_name: '全A股刷新',
          task_type: 'cron',
          schedule: '0 10 * * 1-5',
          status: 'failed',
          output: '',
          error: 'kaboom',
          started_at: '2026-06-16T10:00:00',
          finished_at: '2026-06-16T10:00:08',
          duration_ms: 8400,
          trigger_source: 'auto',
        },
      ],
    });
    mockListTasks.mockResolvedValue([]);
    mockTaskLogsByDate.mockResolvedValue({ success: true, data: [] });
  });

  it('renders header', async () => {
    renderWithProviders(<TaskResults />);
    await waitFor(() => {
      expect(screen.getByText(/任务执行结果/)).toBeInTheDocument();
    });
  });

  it('renders two tabs', async () => {
    renderWithProviders(<TaskResults />);
    await waitFor(() => {
      expect(screen.getByText(/内置调度器/)).toBeInTheDocument();
    });
    expect(screen.getByText(/用户任务/)).toBeInTheDocument();
  });

  it('shows scheduler run rows from API', async () => {
    renderWithProviders(<TaskResults />);
    await waitFor(() => {
      expect(screen.getByText('板块更新')).toBeInTheDocument();
    });
    expect(screen.getByText('全A股刷新')).toBeInTheDocument();
  });
});
