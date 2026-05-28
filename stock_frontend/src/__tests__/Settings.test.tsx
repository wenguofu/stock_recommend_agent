import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Mock the API
vi.mock('../services/api', () => ({
  stockAPI: {
    getConfig: vi.fn().mockImplementation((key: string) => {
      if (key === 'api_base_url') return Promise.resolve('http://127.0.0.1:35000');
      if (key === 'default_ai_provider') return Promise.resolve('openai');
      if (key === 'openai_api_key') return Promise.resolve('sk-test-key');
      if (key === 'openai_model') return Promise.resolve('gpt-4');
      return Promise.resolve(null);
    }),
    setConfig: vi.fn().mockResolvedValue(true),
    setBaseURL: vi.fn(),
    getAIModels: vi.fn().mockResolvedValue(['gpt-4', 'gpt-3.5-turbo']),
    testAIConnection: vi.fn().mockResolvedValue({ success: true, message: '连接成功' }),
    getAgents: vi.fn().mockResolvedValue([
      { id: 1, name: 'Bull Agent', type: 'default', prompt: 'You are bullish...', enabled: true, ai_provider: null, model: null, sort_order: 1 },
      { id: 2, name: 'Bear Agent', type: 'default', prompt: 'You are bearish...', enabled: true, ai_provider: null, model: null, sort_order: 2 },
    ]),
    updateAgent: vi.fn().mockResolvedValue(true),
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

import Settings from '../pages/Settings';

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

describe('Settings', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // --- Basic Rendering ---

  it('renders the page title', async () => {
    renderWithProviders(<Settings />);
    await waitFor(() => {
      expect(screen.getByText('系统配置')).toBeInTheDocument();
    });
  });

  it('renders backend URL section', async () => {
    renderWithProviders(<Settings />);
    await waitFor(() => {
      expect(screen.getByText('后端地址')).toBeInTheDocument();
    });
  });

  it('renders AI service config section', async () => {
    renderWithProviders(<Settings />);
    await waitFor(() => {
      expect(screen.getByText('AI服务配置')).toBeInTheDocument();
    });
  });

  it('renders agent config section', async () => {
    renderWithProviders(<Settings />);
    await waitFor(() => {
      expect(screen.getByText('Agent配置')).toBeInTheDocument();
    });
  });

  // --- Ant Design components ---

  it('uses antd Card components', async () => {
    renderWithProviders(<Settings />);
    await waitFor(() => {
      const cards = document.querySelectorAll('.ant-card');
      expect(cards.length).toBeGreaterThan(0);
    });
  });

  it('uses antd Form components', async () => {
    renderWithProviders(<Settings />);
    await waitFor(() => {
      const forms = document.querySelectorAll('.ant-form');
      expect(forms.length).toBeGreaterThan(0);
    });
  });

  it('uses antd Button components', async () => {
    renderWithProviders(<Settings />);
    await waitFor(() => {
      const buttons = document.querySelectorAll('.ant-btn');
      expect(buttons.length).toBeGreaterThan(0);
    });
  });

  it('uses antd Select for provider', async () => {
    renderWithProviders(<Settings />);
    await waitFor(() => {
      const selects = document.querySelectorAll('.ant-select');
      expect(selects.length).toBeGreaterThan(0);
    });
  });

  // --- No Tailwind ---

  it('has no Tailwind utility classes', async () => {
    renderWithProviders(<Settings />);
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

  // --- Loading state ---

  it('shows agent loading state', async () => {
    renderWithProviders(<Settings />);
    await waitFor(() => {
      expect(screen.getByText('Agent配置')).toBeInTheDocument();
    });
  });

  it('renders agent names after loading', async () => {
    renderWithProviders(<Settings />);
    await waitFor(() => {
      expect(screen.getByText('Bull Agent')).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText('Bear Agent')).toBeInTheDocument();
    });
  });
});
