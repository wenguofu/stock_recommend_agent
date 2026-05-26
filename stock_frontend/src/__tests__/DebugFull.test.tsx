import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import StrategyRecommend from '../pages/StrategyRecommend';

describe('render with providers', () => {
  it('renders', async () => {
    // Mock global fetch
    const origFetch = global.fetch;
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ strategies: [] }),
    }) as any;

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    let error: Error | null = null;
    try {
      render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter><StrategyRecommend /></MemoryRouter>
        </QueryClientProvider>
      );
    } catch (e) {
      error = e as Error;
    }

    global.fetch = origFetch;

    if (error) {
      console.error('RENDER ERROR:', error.message);
      console.error('STACK:', error.stack?.split('\n').slice(0, 5).join('\n'));
    }
    expect(error).toBeNull();
  });
});
