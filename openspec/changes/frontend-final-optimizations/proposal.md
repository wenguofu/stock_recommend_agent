## Why

Four remaining product-review items have not yet been addressed:

1. **CommandPalette is shipped but disabled.** The component is fully implemented
   (page navigation, stock-code search, API commands, ⌘K listener) but
   `Layout.tsx` mounts it with `enabled={false}`, so users see a clickable "搜索 ⌘K"
   button that does nothing when clicked. Dead affordance + dead feature.

2. **Home.tsx and Watchlist.tsx duplicate the same paginated watchlist query.**
   Both pages issue an identical `fetch('/api/watchlist?page=...&pageSize=...')`.
   Switching between them refetches from scratch; the cache is not shared.

3. **PaperAccounts and PaperRankings are sibling pages with overlapping concern.**
   PaperAccounts lists accounts; PaperRankings ranks them. Both are about "how are my
   paper accounts doing?" — split across two URLs forces a navigation hop to compare.

4. **StockDetail.tsx fires 11 queries unconditionally.** Even though the page has
   tabs (K线 / 技术指标 / AI分析 / AI辩论 / 资金流向 / 风险 / 基本面 / 舆情 / 定量估值),
   every `useQuery` runs the moment the page mounts. Most users open one tab and never
   visit the others — those queries are pure waste.

## What Changes

- **CommandPalette**: flip `enabled={false}` to `enabled={true}` in `Layout.tsx`. The
  component already works; no code change to `CommandPalette.tsx` itself.
- **`useWatchlist` hook**: new `src/hooks/useWatchlist.ts` exposes
  `useWatchlist(page, pageSize)` returning `{ data, isLoading, isError, error, refetch }`.
  Both `Home.tsx` and `Watchlist.tsx` migrate their inline `fetch('/api/watchlist?…')`
  call to use the hook. TanStack Query dedupes per `queryKey`.
- **PaperAccounts ranking snippet**: add a compact "收益排名 TOP 3" Card to
  `PaperAccounts.tsx` header area (above the account grid). Top-3 by `total_profit_pct`.
  Keep `/paper/rankings` route intact for the full view; this is a fast-glance
  shortcut, not a replacement.
- **StockDetail lazy-load**: introduce `activeTabKey` state, gate each tab-specific
  query (`fundamentalData`, `sentimentData`, `moneyFlowHistory`, `riskData`, `mlData`,
  `analystData`, `withBenchmarkData`, `profileData`) on the corresponding tab being
  active. Always-on queries: `realtime`, `comprehensive`, `daily`, `watchlist` (for
  the position banner).

## Capabilities

### New Capabilities
- `frontend-watchlist-hook`: shared paginated watchlist hook used by Home + Watchlist.
- `frontend-paper-top3`: at-a-glance top-3 paper account rankings in PaperAccounts.

### Modified Capabilities
- (none — these are pure UX improvements, no requirement-level spec change)

## Impact

- Affected code:
  - **MODIFIED**: `stock_frontend/src/components/Layout.tsx` (CommandPalette enable)
  - **NEW**: `stock_frontend/src/hooks/useWatchlist.ts` + `.test.tsx`
  - **MODIFIED**: `stock_frontend/src/pages/Home.tsx`, `Watchlist.tsx` (use hook)
  - **MODIFIED**: `stock_frontend/src/pages/PaperAccounts.tsx` (top-3 card)
  - **MODIFIED**: `stock_frontend/src/pages/StockDetail.tsx` (tab-gated queries)
- APIs: none
- Dependencies: none (TanStack Query already in use)
- Performance:
  - Home ↔ Watchlist cache sharing eliminates one duplicate fetch per navigation.
  - StockDetail first-paint drops from 11 to 4 queries on cold load.
  - CommandPalette ⌘K now works (was advertised, did nothing).