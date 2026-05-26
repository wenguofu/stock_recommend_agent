import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import StrategyRecommend from '../pages/StrategyRecommend';

describe('debug', () => {
  it('renders without crash', () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { container } = render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter><StrategyRecommend /></MemoryRouter>
      </QueryClientProvider>
    );
    expect(container).toBeTruthy();
  });
});
