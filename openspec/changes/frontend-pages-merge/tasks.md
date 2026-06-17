## 1. Strategy.tsx Removal (TDD Red → Green)

- [x] 1.1 Confirmed `Strategy.tsx` is not imported by any source file other than its own test (grep). Deleted `src/pages/Strategy.tsx` and `src/__tests__/Strategy.test.tsx`.

## 2. TaskCenter Component (TDD Red → Green)

- [x] 2.1 Created `stock_frontend/src/__tests__/TaskCenter.test.tsx` with 4 assertions: page title, two tabs, status-tab sections, results-tab historical runs. Created `stock_frontend/src/pages/TaskCenter.tsx` implementing StatusTab (scheduler + user-tasks) and ResultsTab (date-bound runs + drawer detail). All 4 tests pass.

## 3. Wire-Up

- [x] 3.1 Added `/task-center` route in `App.tsx` rendering `TaskCenter`; added `Navigate` redirects from `/task-execution` and `/task-results` to `/task-center`. Removed unused TaskExecution/TaskResults imports from App.tsx.
- [x] 3.2 Collapsed sidebar in `Layout.tsx`: removed "任务执行" + "任务结果" entries, added single "任务中心" entry pointing to `/task-center`. Removed unused `HistoryOutlined` import.

## 4. Delete Dead Code

- [x] 4.1 Deleted `stock_frontend/src/pages/Strategy.tsx`.
- [x] 4.2 Deleted `stock_frontend/src/__tests__/Strategy.test.tsx`.

## 5. Verification

- [x] 5.1 `RTK_DISABLE=1 npx vitest run`: 306 passed (incl. 4 new TaskCenter tests), 2 pre-existing Watchlist failures unrelated to this change.
- [x] 5.2 `npm run build`: TypeScript compiles, Vite bundles successfully.
- [x] 5.3 `openspec validate --all --strict`: `change/frontend-pages-merge` reports OK.