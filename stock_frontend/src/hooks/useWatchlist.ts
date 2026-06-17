import { useQuery, type UseQueryResult } from '@tanstack/react-query';

export interface WatchlistPage {
  data: Array<{ code: string; name: string; cost_price?: number | null; shares?: number | null }>;
  total: number;
}

const API = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:35000';

/**
 * Paginated watchlist subscription shared by `Home.tsx` and `Watchlist.tsx`.
 *
 * Same `page` + `pageSize` from multiple consumers collapses to one fetch via
 * TanStack Query's per-query-key cache.
 */
export function useWatchlist(
  page: number,
  pageSize: number,
): UseQueryResult<WatchlistPage> {
  return useQuery<WatchlistPage>({
    queryKey: ['watchlist', page, pageSize],
    queryFn: async () => {
      const res = await fetch(`${API}/api/watchlist?page=${page}&pageSize=${pageSize}`);
      if (!res.ok) throw new Error(`watchlist fetch failed: ${res.status}`);
      return res.json();
    },
  });
}