import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const mockSchedulerStatus = vi.fn();
const mockSchedulerRuns = vi.fn();
const mockListTasks = vi.fn();
const mockTaskLogsByDate = vi.fn();

vi.mock('../services/api', () => ({
  stockAPI: {
    schedulerStatus: (...args: unknown[]) => mockSchedulerStatus(...args),
    schedulerRuns: (...args: unknown[]) => mockSchedulerRuns(...args),
    listTasks: (...args: unknown[]) => mockListTasks(...args),
    taskLogsByDate: (...args: unknown[]) => mockTaskLogsByDate(...args),
  },
}));

import TaskCenter from '../pages/TaskCenter';

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockSchedulerStatus.mockResolvedValue({ success: true, tasks: [] });
  mockSchedulerRuns.mockResolvedValue({ success: true, data: [] });
  mockListTasks.mockResolvedValue([]);
  mockTaskLogsByDate.mockResolvedValue({ success: true, data: [] });
});

describe('TaskCenter', () => {
  it('renders the page title', async () => {
    renderWithProviders(<TaskCenter />);
    expect(screen.getByText(/任务中心/)).toBeInTheDocument();
  });

  it('renders two tabs: status and results', async () => {
    renderWithProviders(<TaskCenter />);
    await waitFor(() => {
      expect(screen.getByRole('tab', { name: /执行状态/ })).toBeInTheDocument();
    });
    expect(screen.getByRole('tab', { name: /执行结果/ })).toBeInTheDocument();
  });

  it('shows scheduler + user-tasks sections on the status tab (default)', async () => {
    mockSchedulerStatus.mockResolvedValue({
      success: true,
      tasks: [
        {
          name: 'daily_refresh',
          type: 'data',
          schedule: 'every_1h',
          run_count: 5,
          last_run: '2026-06-17 09:00:00',
          last_output: 'OK',
          last_error: null,
          in_flight: true,
          current_started_at: '2026-06-17 09:00:00',
        },
      ],
    });
    mockListTasks.mockResolvedValue([
      { id: 1, name: 'price_alert_300433', task_type: 'price_alert', codes: ['300433'], schedule: 'every_5m', enabled: true },
    ]);
    renderWithProviders(<TaskCenter />);
    await waitFor(() => {
      expect(screen.getByText('daily_refresh')).toBeInTheDocument();
    });
    expect(screen.getByText('price_alert_300433')).toBeInTheDocument();
  });

  it('shows date picker + historical runs table on the results tab', async () => {
    mockSchedulerRuns.mockResolvedValue({
      success: true,
      data: [
        {
          id: 42,
          task_name: 'daily_refresh',
          task_type: 'data',
          schedule: 'every_1h',
          status: 'success',
          output: 'Refreshed 1234 stocks',
          error: '',
          started_at: '2026-06-17T09:00:00Z',
          finished_at: '2026-06-17T09:00:05Z',
          duration_ms: 5000,
          trigger_source: 'auto',
        },
      ],
    });
    renderWithProviders(<TaskCenter />);
    const resultsTab = screen.getByRole('tab', { name: /执行结果/ });
    resultsTab.click();
    await waitFor(() => {
      expect(screen.getByText('daily_refresh')).toBeInTheDocument();
    });
    expect(screen.getByText('5.0s')).toBeInTheDocument(); // duration_ms formatted
  });
});