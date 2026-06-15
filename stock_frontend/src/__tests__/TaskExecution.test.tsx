import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const mockSchedulerStatus = vi.fn();
const mockListTasks = vi.fn();

vi.mock('../services/api', () => ({
  stockAPI: {
    schedulerStatus: (...args: any[]) => mockSchedulerStatus(...args),
    listTasks: (...args: any[]) => mockListTasks(...args),
  },
}));

import TaskExecution from '../pages/TaskExecution';

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

describe('TaskExecution', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSchedulerStatus.mockResolvedValue({
      success: true,
      tasks: [
        {
          name: '板块更新',
          type: 'cron',
          schedule: '0 9 * * 1-5',
          run_count: 14,
          last_run: '2026-06-16 09:00:13',
          last_output: '已加载 12 个板块',
          last_error: null,
          in_flight: false,
          current_started_at: null,
        },
      ],
    });
    mockListTasks.mockResolvedValue([]);
  });

  it('renders header title and tabs', async () => {
    renderWithProviders(<TaskExecution />);
    await waitFor(() => {
      expect(screen.getByText(/任务执行/)).toBeInTheDocument();
    });
    expect(screen.getByText(/内置调度器/)).toBeInTheDocument();
    expect(screen.getByText(/用户任务/)).toBeInTheDocument();
  });

  it('shows a task name from scheduler status', async () => {
    renderWithProviders(<TaskExecution />);
    await waitFor(() => {
      expect(screen.getByText('板块更新')).toBeInTheDocument();
    });
  });

  it('has a refresh button', async () => {
    renderWithProviders(<TaskExecution />);
    const btn = await screen.findByRole('button', { name: /刷新/ });
    expect(btn).toBeInTheDocument();
  });

  it('refresh button refetches data', async () => {
    renderWithProviders(<TaskExecution />);
    const btn = await screen.findByRole('button', { name: /刷新/ });
    fireEvent.click(btn);
    await waitFor(() => {
      expect(mockSchedulerStatus.mock.calls.length).toBeGreaterThanOrEqual(2);
    });
  });
});
