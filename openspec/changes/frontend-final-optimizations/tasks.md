## 1. CommandPalette enable (P2)

- [x] 1.1 Flipped `enabled={false}` → `enabled` in `Layout.tsx`. ⌘K / Ctrl+K now opens
  the command palette (it was previously advertised but disabled).

## 2. useWatchlist hook (P1)

- [x] 2.1 Wrote failing test `useWatchlist.test.tsx` (3 scenarios). RED: import fails.
- [x] 2.2 Implemented `useWatchlist.ts`. GREEN: 3/3 tests pass.
- [x] 2.3 Migrated `Home.tsx` (line 38-44) and `Watchlist.tsx` (line 83-87) inline
  fetch calls to the new hook. Both pages now share one cache slot per (page, pageSize).

## 3. PaperAccounts top-3 card (P2)

- [x] 3.1 Added top-3 ranking card above account grid in `PaperAccounts.tsx`. Renders
  only when ≥3 accounts exist; sorts by `total_profit_pct` desc; shows 🥇🥈🥉 medals.
  "查看完整排名 →" link navigates to `/paper/rankings`.

## 4. StockDetail tab-gated queries (P1)

- [x] 4.1 Added `activeTabKey` state with default `'chart'`; wired to `<Tabs activeKey onChange>`.
- [x] 4.2 Gated 8 queries on `tabActivated('<tab-key>')`:
  - `fundamentalData`, `profileData`, `analystData` → `tabActivated('fundamental')`
  - `sentimentData` → `tabActivated('sentiment')`
  - `moneyFlowHistory` → `tabActivated('moneyflow')`
  - `riskData`, `mlData` → `tabActivated('risk')`
  - `withBenchmarkData` → `tabActivated('chart')`
  Always-on (no gate): `realtimeData`, `comprehensiveData`, `dailyData`, `watchlistData`.

## 5. Verification

- [x] 5.1 `RTK_DISABLE=1 npx vitest run`: 309 passed (incl. 4 useRealtimeQuote + 3 useWatchlist +
  4 TaskCenter = 11 new tests across all changes), 2 pre-existing Watchlist failures
  unrelated to this change.
- [x] 5.2 `npm run build`: TypeScript + Vite compile clean.
- [x] 5.3 `openspec validate --all --strict`: `change/frontend-final-optimizations` passes.