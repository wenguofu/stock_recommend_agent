## Context

`Strategy.tsx` predates the multi-tab refactor that produced `StrategyRecommend.tsx`.
It still ships in the bundle and ships with its own test, but no route renders it
anymore. Carrying two implementations of "强势股筛选" invites drift — bug fixes in one
file are missed in the other, and new strategies are only added to the live one.

`TaskExecution.tsx` (status, current) and `TaskResults.tsx` (historical by date) both
target the scheduler + user-task model. They were landed as two separate pages for
ergonomic reasons but together they are one logical surface: "task runs". The current
split forces the user to mentally classify a question (current vs historical) before
they know which page to open — a UX tax that buys nothing.

## Goals / Non-Goals

**Goals:**
- Remove the dead `Strategy.tsx` page; keep `StrategyRecommend.tsx` as the single
  implementation behind `/strategy`.
- Replace the two-task-pages navigation with one "任务中心" entry. The new
  `TaskCenter.tsx` page uses Tabs to switch between current status and historical
  results, with the existing date picker preserved on the historical tab.
- Preserve every existing user-visible capability (current status list, run counts,
  elapsed timer, date-bound scheduler-runs + user-task-logs, drawer detail view).
- Keep `/task-execution` and `/task-results` as redirects so any external bookmarks,
  notification links, or test references still resolve.

**Non-Goals:**
- Changing backend APIs.
- Restructuring the scheduler or task model.
- Migrating `Tasks.tsx` (which handles price-alert + AI-analysis user task *creation*
  and *configuration*) — different concern.

## Decisions

1. **Delete rather than merge Strategy.tsx** — `/strategy` already routes to
   `StrategyRecommend.tsx`, which contains the same `strong_stocks` strategy plus
   two more (十倍潜力 / 突破形态). Strategy.tsx adds no capability. The unit test
   is also deleted — its assertions are already covered by
   `StrategyRecommend.test.tsx`.

   *Alternative considered:* keep Strategy.tsx as a "legacy" page. Rejected: dead
   code with active test maintenance is worse than no code.

2. **TaskCenter uses internal Tabs, not a separate route per concern** — current
   status and historical results share the same data sources (scheduler status +
   user-tasks list). Splitting them across URLs doubles navigation state and
   forces a full reload when switching contexts. A Tab switch is instant.

   *Alternative considered:* keep two pages, just rename. Rejected: doesn't fix
   the navigation-tax problem.

3. **Redirects via React Router `Navigate` component** — the cheapest way to
   preserve old URLs without breaking `BrowserRouter` state. Bookmarks land on
   `/task-center`; the `Navigate` redirect is invisible to the user.

   *Alternative considered:* server-side 301. Rejected: this is a pure SPA;
   server-side redirect is out of scope.

4. **Sidebar collapses to one entry** — "任务执行" and "任务结果" entries merge into
   "任务中心" pointing at `/task-center`. `/tasks` (user task *creation*) stays
   as-is — different concern.

## Risks / Trade-offs

- [Old route users land on `/task-center` instead of one of the two pages.] →
  Mitigation: redirect is automatic; the new page covers both prior scopes via tabs.
- [Test references to deleted `Strategy.tsx`] → Mitigation: deleted in this change;
  no other source file imports `Strategy.tsx` (verified via grep — only its own
  test does).
- [Drawer detail view state migration.] → Mitigation: drawer state stays local to
  `TaskCenter.tsx`; switching tabs resets the drawer, which is acceptable for a
  list-detail interaction.

## Migration Plan

1. Land `TaskCenter.tsx` + tests.
2. Wire `/task-center` in `App.tsx`; redirect old routes via `Navigate`.
3. Collapse sidebar entries in `Layout.tsx`.
4. Delete `Strategy.tsx` + its test.
5. Run full Vitest suite + `npm run build` to confirm no regressions.

Rollback: revert the four-file diff. No backend or migration concerns.

## Open Questions

- Should we also redirect `/tasks` (user task creation) into `/task-center`? —
  *Decision: no. `Tasks.tsx` is CRUD for user-defined tasks, not execution status;
  merging would conflate two distinct workflows.*