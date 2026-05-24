import { describe, it, expect, vi } from 'vitest';

// Mock fetch
const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

describe('StockAPI', () => {
  let stockAPI: any;

  beforeAll(async () => {
    // 动态导入以控制 mock 时机
    const mod = await import('../services/api');
    stockAPI = mod.stockAPI;
  });

  beforeEach(() => {
    mockFetch.mockReset();
  });

  it('应该导出 stockAPI 实例', () => {
    expect(stockAPI).toBeDefined();
    expect(typeof stockAPI.getRealtime).toBe('function');
    expect(typeof stockAPI.getWatchlist).toBe('function');
  });

  it('getRealtime 调用正确端点', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ data: { code: '000001', current_price: 12.5 } }),
    });

    const result = await stockAPI.getRealtime('000001');
    expect(result.code).toBe('000001');
    expect(result.current_price).toBe(12.5);
    expect(mockFetch).toHaveBeenCalledTimes(1);

    const url = mockFetch.mock.calls[0][0];
    expect(url).toContain('/api/sina/realtime/000001');
  });

  it('getWatchlist 调用正确端点', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ data: [{ code: '300679', name: '电连技术' }] }),
    });

    const result = await stockAPI.getWatchlist();
    expect(result).toHaveLength(1);
    expect(result[0].code).toBe('300679');
    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(mockFetch.mock.calls[0][0]).toContain('/api/watchlist');
  });

  it('getDebateJobStatus 调用正确端点', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        data: { job_id: 'abc123', status: 'completed', progress: 100 }
      }),
    });

    const result = await stockAPI.getDebateJobStatus('abc123');
    expect(result.status).toBe('completed');
    expect(mockFetch.mock.calls[0][0]).toContain('/api/ai/debate/status/abc123');
  });

  it('API 错误应抛出异常', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      statusText: 'Not Found',
    });

    await expect(stockAPI.getRealtime('invalid')).rejects.toThrow();
  });
});
