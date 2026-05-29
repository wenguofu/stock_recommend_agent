/**
 * 自选股状态管理 — 乐观更新
 */
import { create } from 'zustand';
import { stockAPI } from '../services/api';
import type { WatchlistItem } from '../services/api';

interface WatchlistState {
  items: WatchlistItem[];
  loading: boolean;
  error: string | null;
  fetchWatchlist: () => Promise<void>;
  addStock: (code: string, name?: string, cost_price?: number | null, shares?: number | null) => Promise<void>;
  removeStock: (code: string) => Promise<void>;
  updateOrder: (orders: Array<{ code: string; sort_order: number }>) => Promise<void>;
  updatePosition: (code: string, cost_price: number, shares: number) => Promise<void>;
}

export const useWatchlistStore = create<WatchlistState>((set, get) => ({
  items: [],
  loading: false,
  error: null,

  fetchWatchlist: async () => {
    set({ loading: true, error: null });
    try {
      const items = await stockAPI.getWatchlist();
      set({ items, loading: false });
    } catch (error) {
      set({ error: (error as Error).message, loading: false });
    }
  },

  addStock: async (code: string, name?: string, cost_price?: number | null, shares?: number | null) => {
    const prevItems = get().items;
    // 乐观更新：立即添加到UI
    const optimisticItem: WatchlistItem = {
      id: Date.now(), // temporary id
      code,
      name: name || code,
      cost_price: cost_price ?? undefined,
      shares: shares ?? undefined,
      sort_order: prevItems.length,
    };
    set({ items: [...prevItems, optimisticItem], error: null });

    try {
      await stockAPI.addWatchlist(code, name, cost_price, shares);
      // 后台同步真实数据
      await get().fetchWatchlist();
    } catch (error) {
      // 回滚
      set({ items: prevItems, error: (error as Error).message });
    }
  },

  removeStock: async (code: string) => {
    const prevItems = get().items;
    // 乐观更新：立即从UI移除
    set({ items: prevItems.filter(i => i.code !== code), error: null });

    try {
      await stockAPI.removeWatchlist(code);
    } catch (error) {
      // 回滚
      set({ items: prevItems, error: (error as Error).message });
    }
  },

  updateOrder: async (orders: Array<{ code: string; sort_order: number }>) => {
    const prevItems = get().items;
    try {
      await stockAPI.updateWatchlistOrder(orders);
      await get().fetchWatchlist();
    } catch (error) {
      set({ error: (error as Error).message });
    }
  },

  updatePosition: async (code: string, cost_price: number, shares: number) => {
    const prevItems = get().items;
    // 乐观更新
    set({
      items: prevItems.map(i =>
        i.code === code ? { ...i, cost_price, shares } : i
      ),
    });
    try {
      await stockAPI.updateWatchlistPosition(code, cost_price, shares);
    } catch (error) {
      set({ items: prevItems, error: (error as Error).message });
    }
  },
}));
