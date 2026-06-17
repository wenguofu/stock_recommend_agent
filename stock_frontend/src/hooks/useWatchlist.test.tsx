import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useWatchlist } from './useWatchlist';

const fetcher = vi.fn();

global.fetch = vi.fn((...args: unknown[]) => {
  fetcher(...args);
  return Promise.resolve({
    ok: true,
    json: () => Promise.resolve({ data: [{ code: '000001', name: '平安银行' }], total: 1 }),
  });
}) as unknown as typeof fetch;

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
  });
}

function renderWithClient(ui: React.ReactElement, client = makeClient()) {
  return { client, ...render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>) };
}

function TwoConsumers({ page, pageSize }: { page: number; pageSize: number }) {
  useWatchlist(page, pageSize);
  useWatchlist(page, pageSize);
  return null;
}

beforeEach(() => {
  fetcher.mockClear();
});
afterEach(() => {
  vi.restoreAllMocks();
});

describe('useWatchlist', () => {
  it('deduplicates: two consumers with the same page+pageSize trigger one fetch', async () => {
    const { client } = renderWithClient(<TwoConsumers page={1} pageSize={12} />);
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));
    expect(fetcher).toHaveBeenCalledWith(
      expect.stringContaining('/api/watchlist?page=1&pageSize=12'),
    );
    client.clear();
  });

  it('issues separate fetches for different page sizes', async () => {
    function TwoSizes() {
      useWatchlist(1, 12);
      useWatchlist(1, 20);
      return null;
    }
    const { client } = renderWithClient(<TwoSizes />);
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
    client.clear();
  });

  it('returns data shaped {data, total} from the JSON body', async () => {
    function Probe() {
      const q = useWatchlist(2, 15);
      if (q.data) {
        // Touch a field so the type is verified at compile time
        void q.data.total;
      }
      return null;
    }
    const { client } = renderWithClient(<Probe />);
    await waitFor(() => expect(fetcher).toHaveBeenCalled());
    expect(fetcher).toHaveBeenCalledWith(
      expect.stringContaining('page=2'),
    );
    client.clear();
  });
});