import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useRealtimeQuote } from './useRealtimeQuote';

// Spy that records every invocation of the realtime fetcher.
const fetcher = vi.fn();

vi.mock('../services/api', () => ({
  stockAPI: {
    getRealtime: (...args: unknown[]) => {
      fetcher(...args);
      return Promise.resolve({
        code: args[0] as string,
        name: 'mock',
        current_price: 10,
        change_percent: 0,
        volume: 0,
        amount: 0,
        high: 0,
        low: 0,
        open: 0,
        yesterday_close: 10,
        turnover_rate: 0,
      });
    },
  },
}));

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
  });
}

function renderWithClient(ui: React.ReactElement, client = makeClient()) {
  return { client, ...render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>) };
}

function TwoConsumers({ code }: { code: string }) {
  // Two components reading the same code — must share one fetch.
  useRealtimeQuote(code);
  useRealtimeQuote(code);
  return null;
}

beforeEach(() => {
  fetcher.mockClear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('useRealtimeQuote', () => {
  it('deduplicates: two consumers of the same code trigger exactly one fetch', async () => {
    const { client } = renderWithClient(<TwoConsumers code="000001" />);
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));
    expect(fetcher).toHaveBeenCalledWith('000001');
    client.clear();
  });

  it('does not fetch when code is empty', async () => {
    function Empty() {
      useRealtimeQuote('');
      return null;
    }
    const { client } = renderWithClient(<Empty />);
    // Give React Query a tick to (not) run.
    await new Promise((r) => setTimeout(r, 50));
    expect(fetcher).not.toHaveBeenCalled();
    client.clear();
  });

  it('issues separate fetches for distinct codes', async () => {
    function TwoCodes() {
      useRealtimeQuote('000001');
      useRealtimeQuote('000002');
      return null;
    }
    const { client } = renderWithClient(<TwoCodes />);
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
    expect(fetcher).toHaveBeenCalledWith('000001');
    expect(fetcher).toHaveBeenCalledWith('000002');
    client.clear();
  });

  it('exposes loading state until data resolves', async () => {
    let capturedLoading = false;
    function Probe() {
      const q = useRealtimeQuote('600519');
      capturedLoading = q.isLoading;
      return null;
    }
    const { client } = renderWithClient(<Probe />);
    await waitFor(() => expect(fetcher).toHaveBeenCalled());
    await waitFor(() => expect(capturedLoading).toBe(false));
    client.clear();
  });
});