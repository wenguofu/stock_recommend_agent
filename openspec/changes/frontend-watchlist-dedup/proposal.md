## Why

`Watchlist.tsx` currently mounts three independent cell components (`WatchlistPriceCell`,
`WatchlistChangeCell`, `WatchlistPnlCell`) for every row, each calling
`useQuery({ queryKey: ['realtime', code] })` independently. With N watchlist stocks, the page
issues **3N identical requests** to `/api/sina/realtime/{code}` on every refetch cycle, with
each cell maintaining its own refetch timer. The data is the same — only the render differs.
This wastes backend cycles, blows up Redis cache key count, and produces redundant network
traffic during trading hours when the 5-second refresh interval is in effect.

## What Changes

- Add `useRealtimeQuote(code)` hook in `stock_frontend/src/hooks/` that owns **one** shared
  `useQuery(['realtime', code])` per stock code, with the existing trading-hours-aware
  refetch interval (`5000` ms during A-share trading hours, `60000` ms otherwise).
- Refactor `Watchlist.tsx` so the three cell components consume the same hook output via
  TanStack Query's automatic query-key deduplication (one fetch per `code` per refetch tick,
  regardless of how many cells read it).
- Add a Vitest test suite `useRealtimeQuote.test.tsx` that verifies:
  - Multiple consumers sharing the same `code` cause **exactly one** fetch.
  - `enabled: false` short-circuits the fetch.
  - Empty / null `code` is rejected.
- No public API or backend contract change. Pure frontend refactor + new hook.

## Capabilities

### New Capabilities
- `frontend-realtime-hook`: Shared TanStack Query hook for per-stock realtime quotes,
  consumed by watchlist cells, home page cards, and any future single-stock UI surfaces.

### Modified Capabilities
- (none — no spec-level requirement change; this is an internal implementation refactor)

## Impact

- Affected code:
  - **NEW**: `stock_frontend/src/hooks/useRealtimeQuote.ts`,
    `stock_frontend/src/hooks/useRealtimeQuote.test.tsx`
  - **MODIFIED**: `stock_frontend/src/pages/Watchlist.tsx` (cell components collapse to
    consumers of the new hook)
- APIs: none (frontend-only)
- Dependencies: none (already uses `@tanstack/react-query`)
- Performance: request count for an N-stock watchlist drops from `3N` → `N` per refetch
  tick; backend `/api/sina/realtime/{code}` calls drop ~67%.
- Risk: low — purely frontend; existing tests for `Watchlist.tsx` must continue to pass.