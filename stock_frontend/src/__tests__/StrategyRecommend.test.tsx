import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import StrategyRecommend from '../pages/StrategyRecommend';

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

function renderWithProviders(ui: React.ReactElement) {
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/']}>{ui}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe('StrategyRecommend', () => {
  it('renders without crashing', () => {
    const { container } = renderWithProviders(<StrategyRecommend />);
    expect(container).toBeTruthy();
  });

  it('uses antd components', () => {
    const { container } = renderWithProviders(<StrategyRecommend />);
    expect(container.querySelector('.ant-space')).toBeTruthy();
  });
});
