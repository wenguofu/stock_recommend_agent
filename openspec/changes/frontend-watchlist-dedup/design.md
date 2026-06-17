## Context

`Watchlist.tsx` mounts three independent cell components per row
(`WatchlistPriceCell`, `WatchlistChangeCell`, `WatchlistPnlCell`). Each calls
`useQuery({ queryKey: ['realtime', code] })` directly inside its own function body.
Because each `useQuery` call registers a separate observer against the QueryClient cache,
React Query cannot deduplicate them — it sees three independent subscriptions, each with
its own refetch timer, and fires the fetcher three times per row per tick.

TanStack Query's cache is **per-query-key** — multiple consumers sharing the same key
collapse to one fetch automatically — but only when those consumers reuse the same hook
function and observe the same `queryKey` from a shared `QueryClient`. Right now each
component duplicates the query literal inline, so the cache layer never gets the chance to
dedupe.

`Home.tsx` and `StockCard` independently repeat the same `useQuery(['realtime', code])`
pattern. A shared hook lifts the deduplication across pages, not just within a row.

## Goals / Non-Goals

**Goals:**
- One network fetch per `(code, refetch-tick)` regardless of how many cells observe it.
- Drop-in replacement for the existing inline `useQuery` calls in `Watchlist.tsx` (and
  ready-to-use in `Home.tsx`, `StockCard`, etc.).
- Preserve trading-hours-aware refetch interval (5000 ms during A-share trading hours,
  60000 ms otherwise).
- Test coverage that proves deduplication: multiple `useRealtimeQuote(code)` consumers
  trigger exactly one `fetcher` call.

**Non-Goals:**
- Replacing TanStack Query with another state library.
- Changing the underlying `/api/sina/realtime/{code}` contract.
- Migrating `Home.tsx` or other pages in this change (out of scope; this change only
  establishes the hook + refactors `Watchlist.tsx`).

## Decisions

1. **Shared hook with internal query-key construction** — `useRealtimeQuote(code)` is a
   thin wrapper around `useQuery({ queryKey: ['realtime', code] })`. Centralizing the
   key guarantees every consumer agrees on the cache slot.

   *Alternatives considered:*
   - *Hoist the query to the row level and pass data down.* Rejected: requires
     re-shaping `Watchlist.tsx`'s columns config to accept a render-prop or data
     object per row; larger blast radius.
   - *Use `select` to project different fields per cell.* Tempting, but `select` runs
     per-observer, so it does not reduce fetches — only rerenders. Same dedup win
     comes from sharing the key, which `select` doesn't enable.

2. **`enabled` short-circuits on empty code** — when `code` is falsy, the hook returns
   `enabled: false` so no fetcher fires. The current cells already gate with `!!code`
   inline; the hook centralizes this guard so callers can't forget.

3. **`staleTime` defaults** — kept the existing implicit `0` (i.e. always consider
   data stale, refetch on schedule). Introducing a positive `staleTime` would change
   semantics and surprise existing consumers; out of scope.

4. **Trading-hours interval logic stays in the hook** — keeps the time-of-day branch
   in one place. The `isTradingTime()` / `getRefetchInterval()` helpers in `Watchlist.tsx`
   move into the hook file (or are inlined; either is acceptable — see Risks).

## Risks / Trade-offs

- [Hook semantics drift risk: callers may pass stale code.] → Mitigation: `enabled`
  guard at hook entry; consumers cannot bypass it.
- [Behavior change in refetch interval is unlikely but possible if the helpers move.]
  → Mitigation: keep helpers in `Watchlist.tsx` for now (no extraction); the hook takes
  `refetchInterval` as a parameter, defaulting to `getRefetchInterval()`.
- [Test brittleness around `vi.advanceTimersByTime` for refetch intervals.] →
  Mitigation: tests focus on **dedup count** (one fetch per code) rather than on
  timer-driven behavior, which keeps the suite fast and deterministic.

## Migration Plan

1. Land `useRealtimeQuote` hook + test suite (no consumer changes yet).
2. Refactor `Watchlist.tsx` three cell components to use the hook.
3. Run full Vitest suite (`RTK_DISABLE=1 npx vitest run`) — all existing tests must
   still pass.
4. (Future PR) migrate `Home.tsx` `StockCard` and other consumers — out of scope here.

Rollback: trivial — revert the two files. No backend or migration concerns.

## Open Questions

- Should `Home.tsx`'s `useWatchlistStore`-driven cards also adopt the new hook in this
  change? — *Decision: defer; this change ships the hook + watchlist only, to keep
  the diff focused and testable.*