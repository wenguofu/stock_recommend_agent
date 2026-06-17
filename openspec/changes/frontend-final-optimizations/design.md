## Context

Each of the four items is a small, well-scoped change. None requires architectural
rework; each can be verified independently. They are grouped into one OpenSpec change
so reviewers see the full picture, but tasks.md sequences them so each can land in
isolation if needed.

## Goals / Non-Goals

**Goals:**
- CommandPalette ⌘K shortcut works for users.
- Home and Watchlist share one watchlist cache slot.
- PaperAccounts page surfaces a quick-glance top-3 ranking.
- StockDetail first paint only fetches data for the visible tab.

**Non-Goals:**
- Replacing CommandPalette with a different UI.
- Changing the watchlist API or pagination contract.
- Removing `/paper/rankings` (the full ranking page stays).
- Refactoring StockDetail into per-tab subcomponents (out of scope — would be a
  follow-up refactor).

## Decisions

1. **CommandPalette: enable, don't rewrite.** The component already implements page
   navigation, stock search, and ⌘K listener. `Layout.tsx` passes `enabled={false}`
   for reasons lost to history. Flipping the boolean delivers the feature with zero
   risk.

2. **`useWatchlist` returns `{ data, isLoading, isError, error, refetch }`.**
   Matches the shape of `useQuery` so the call sites change minimally: replace
   `fetch().then(r => r.json())` with the hook. The hook owns the `queryKey` so cache
   dedup is automatic across pages.

3. **PaperAccounts top-3 ranking lives in the page, not a new hook.** A single
   `useQuery(['paper-rankings-top3'])` inside the page is enough; if we generalize
   later, extracting is trivial.

4. **StockDetail: gate queries on `activeTabKey` not `defaultActiveTab`.**
   `Tabs` `items` accept `key`; default active key is `'chart'`. So on initial load,
   only the chart tab's queries fire. As the user clicks through, other tabs mount
   their queries. Tab state lives at the page level (single useState); per-tab child
   components stay in-page to keep the diff small.

## Risks / Trade-offs

- [Tab-switch flicker on first visit of a tab] → the tab mount triggers its queries;
  antd Tabs default to `destroyInactiveTabPane=false`, so already-visited tabs retain
  cached data. Acceptable.
- [useWatchlist refetch on page-size change] → preserved; hook signature includes page,
  pageSize in queryKey.
- [CommandPalette ⌘K conflicts with browser search shortcut in some browsers] → known
  behavior; the handler explicitly calls `preventDefault()`.

## Migration Plan

1. Land useWatchlist hook + tests (TDD).
2. Migrate Home + Watchlist to use the hook.
3. Add top-3 ranking card to PaperAccounts.
4. Enable CommandPalette in Layout.
5. Gate StockDetail queries on tab activation.
6. Run full Vitest + npm run build + openspec validate.

Rollback: per-file revert, no backend or migration concerns.