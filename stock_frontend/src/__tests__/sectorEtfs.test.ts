import { describe, it, expect } from 'vitest';
import { findEtfs, SECTOR_ETFS } from '../constants/sectorEtfs';

describe('SECTOR_ETFS', () => {
  it('应该包含常见板块映射', () => {
    expect(SECTOR_ETFS['半导体']).toBeDefined();
    expect(SECTOR_ETFS['消费电子']).toBeDefined();
    expect(SECTOR_ETFS['人工智能']).toBeDefined();
  });

  it('每个板块至少有一个ETF', () => {
    for (const [key, etfs] of Object.entries(SECTOR_ETFS)) {
      expect(etfs.length).toBeGreaterThan(0);
    }
  });
});

describe('findEtfs', () => {
  it('精确匹配返回对应ETF', () => {
    const result = findEtfs('半导体');
    expect(result).toBeDefined();
    expect(result![0].name).toBe('芯片ETF');
  });

  it('缩略名匹配', () => {
    const result = findEtfs('人工智能AI');
    expect(result).toBeDefined();
  });

  it('模糊匹配 — 包含关系', () => {
    const result = findEtfs('芯片半导体板块');
    expect(result).toBeDefined();
  });

  it('无匹配返回 undefined', () => {
    const result = findEtfs('不存在的板块名');
    expect(result).toBeUndefined();
  });

  it('所有ETF代码为6位数字', () => {
    for (const [, etfs] of Object.entries(SECTOR_ETFS)) {
      for (const etf of etfs) {
        expect(etf.code).toMatch(/^\d{6}$/);
      }
    }
  });
});
