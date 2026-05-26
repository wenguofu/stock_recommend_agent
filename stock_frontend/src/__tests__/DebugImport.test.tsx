import { describe, it, expect } from 'vitest';
import StrategyRecommend from '../pages/StrategyRecommend';

describe('component import', () => {
  it('imports successfully', () => {
    expect(StrategyRecommend).toBeDefined();
    expect(typeof StrategyRecommend).toBe('function');
  });
});
