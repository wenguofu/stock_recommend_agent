import { useQuery, type UseQueryResult } from '@tanstack/react-query';
import { stockAPI, type StockRealtime } from '../services/api';

/**
 * True if the current local time falls inside A-share trading hours (Mon-Fri).
 * Trading sessions: 09:30-11:30 and 13:00-15:00 local time.
 */
function isTradingTime(): boolean {
  const now = new Date();
  const hour = now.getHours();
  const minute = now.getMinutes();
  const day = now.getDay();
  if (day === 0 || day === 6) return false;
  const morning =
    (hour === 9 && minute >= 30) || (hour > 9 && hour < 11) || (hour === 11 && minute <= 30);
  const afternoon = hour >= 13 && hour < 15;
  return morning || afternoon;
}

/** 5s during trading hours, 60s otherwise. */
function getRefetchInterval(): number {
  return isTradingTime() ? 5000 : 60000;
}

/**
 * Subscribe to `/api/sina/realtime/{code}` via TanStack Query.
 *
 * Multiple consumers calling this hook with the same `code` share a single query
 * subscription (cache key `['realtime', code]`), so the fetcher runs exactly once
 * per refetch tick — regardless of how many cells or components observe it.
 *
 * Pass `''` (or any falsy value) to short-circuit; the hook returns
 * `enabled: false` and does not fire the fetcher.
 */
export function useRealtimeQuote(code: string | undefined | null): UseQueryResult<StockRealtime> {
  const enabled = !!code && typeof code === 'string' && code.length > 0;
  return useQuery<StockRealtime>({
    queryKey: ['realtime', code],
    queryFn: () => stockAPI.getRealtime(code as string),
    enabled,
    refetchInterval: getRefetchInterval(),
  });
}