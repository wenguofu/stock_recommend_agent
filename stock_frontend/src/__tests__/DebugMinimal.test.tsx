import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import StrategyRecommend from '../pages/StrategyRecommend';

describe('minimal render', () => {
  it('renders without providers', () => {
    expect(() => {
      render(<MemoryRouter><StrategyRecommend /></MemoryRouter>);
    }).toThrow();
  });
});
