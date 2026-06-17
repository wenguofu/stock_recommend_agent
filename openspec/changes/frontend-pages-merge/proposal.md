## Why

Two pieces of frontend surface area are duplicated or fragmented:

1. **Strategy.tsx (560 lines) is dead code.** The route table maps `/strategy` to
   `StrategyRecommend.tsx` (a more complete three-tab implementation: 强势股 / 十倍潜力 / 突破形态).
   `Strategy.tsx` is only referenced by its own unit test — no live route, no navigation
   entry. Maintenance cost is double: bug fixes, schema drift, and feature work all have to
   be applied twice.

2. **TaskExecution.tsx and TaskResults.tsx split one logical feature across two URLs.**
   Both read the same `scheduler-status` / `scheduler-runs` / user-task logs APIs and
   present scheduler runs + user-task runs. `TaskExecution` shows *current* status,
   `TaskResults` shows *historical* runs by date — same data model, two pages, two
   navigation entries (`/task-execution`, `/task-results`). Users have to remember which
   one holds the answer to "what happened yesterday?".

## What Changes

- **DELETE** `stock_frontend/src/pages/Strategy.tsx` and
  `stock_frontend/src/__tests__/Strategy.test.tsx`. Live route `/strategy` already
  renders `StrategyRecommend.tsx`; no user-visible behavior changes.
- **MERGE** `TaskExecution.tsx` and `TaskResults.tsx` into a single new component
  `stock_frontend/src/pages/TaskCenter.tsx` with internal Tabs:
  - Tab "执行状态" (current/in-flight, no date filter) ← `TaskExecution` scheduler + user tabs
  - Tab "执行结果" (historical by date, drawer details) ← `TaskResults` scheduler + user tabs
- **UPDATE** `stock_frontend/src/App.tsx`: route `/task-center` renders `TaskCenter`;
  `/task-execution` and `/task-results` redirect to `/task-center` (via the existing
  React Router `Navigate` mechanism) so any bookmarks stay functional.
- **UPDATE** `stock_frontend/src/components/Layout.tsx`: collapse the two sidebar entries
  ("任务执行" + "任务结果") into one "任务中心" entry pointing at `/task-center`.

## Capabilities

### New Capabilities
- `frontend-task-center`: Unified task center page consolidating current execution status
  and historical results, with internal tabs and a date picker for historical lookups.

### Modified Capabilities
- (none — no spec-level requirement change; this is a UI consolidation refactor)

## Impact

- Affected code:
  - **DELETED**: `stock_frontend/src/pages/Strategy.tsx`,
    `stock_frontend/src/__tests__/Strategy.test.tsx`
  - **NEW**: `stock_frontend/src/pages/TaskCenter.tsx`,
    `stock_frontend/src/__tests__/TaskCenter.test.tsx`
  - **MODIFIED**: `stock_frontend/src/App.tsx` (routes + redirects),
    `stock_frontend/src/components/Layout.tsx` (sidebar)
- APIs: none
- Dependencies: none
- Risk: low — old routes redirect; live `/strategy` route behavior preserved by existing
  `StrategyRecommend.tsx`.