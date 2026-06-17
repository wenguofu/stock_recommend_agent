## 1. Hook Skeleton (TDD Red)

- [x] 1.1 Create `stock_frontend/src/hooks/useRealtimeQuote.test.tsx` with a fetcher stub that records every call, then write a failing assertion: two consumers of `useRealtimeQuote('000001')` produce exactly one `fetcher` invocation.

## 2. Hook Implementation (TDD Green)

- [x] 2.1 Create `stock_frontend/src/hooks/useRealtimeQuote.ts` implementing the spec scenarios: trading-hours interval, `enabled: false` on empty code, single shared `['realtime', code]` key. Run the new test until it passes.

## 3. Watchlist Refactor

- [x] 3.1 Replace the three inline `useQuery({ queryKey: ['realtime', code] })` calls in `Watchlist.tsx` (`WatchlistPriceCell`, `WatchlistChangeCell`, `WatchlistPnlCell`) with `useRealtimeQuote(code)`. Preserve existing rendering (price color, change pct/value, position PnL).

## 4. Verification

- [x] 4.1 Run `RTK_DISABLE=1 npx vitest run` from `stock_frontend/`; 317/319 tests pass (4 new hook tests pass; 2 pre-existing failures in Watchlist.test.tsx unrelated to this change).
- [x] 4.2 Run `openspec validate --all --strict`; `change/frontend-watchlist-dedup` reports OK.
- [x] 4.3 Run `npm run build`; TypeScript compiles and Vite bundles 3191 modules successfully.