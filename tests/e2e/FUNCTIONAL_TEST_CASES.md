# 📋 Functional Test Cases — Frontend Optimization Verification

> Mapped 1-to-1 from the 7 product-review issues fixed across three OpenSpec
> changes: `frontend-watchlist-dedup`, `frontend-pages-merge`,
> `frontend-final-optimizations`.
>
> **Backend**: `http://127.0.0.1:35000` (Flask + frontend `dist/`)
> **Browser**: Chromium via Playwright (Python)
> **Test runner**: `tests/e2e/portal_e2e.py`

---

## Round 1 — `frontend-watchlist-dedup`

### TC-1.1 — Watchlist realtime price column loads
**Maps to**: Issue #3 (Watchlist 3N duplicate API)
**Pre**: Backend healthy, at least one stock in watchlist
**Steps**:
1. Navigate to `/watchlist`
2. Wait for table to render
3. Read first row's price cell

**Expected**:
- Page renders within 5 s
- Price cell shows a number (not `--`)
- Network tab shows exactly **1** call per row to `/api/sina/realtime/{code}`
  (vs. 3 before optimization)

### TC-1.2 — Watchlist change/pnl cells share the same fetch
**Maps to**: Issue #3
**Steps**:
1. From TC-1.1 state, observe network requests during a 5-second window
2. Count distinct `/api/sina/realtime/{code}` calls per code

**Expected**:
- Exactly **1** request per code per refetch tick
- No duplicate fetches even though 3 cells observe the same code

### TC-1.3 — Empty code short-circuits
**Maps to**: Spec: `useRealtimeQuote` empty-code guard
**Steps**:
1. Watchlist with 0 stocks
2. Page must not issue any `/api/sina/realtime/...` request

**Expected**:
- Zero realtime API calls

---

## Round 2 — `frontend-pages-merge`

### TC-2.1 — Strategy.tsx is gone, /strategy still works
**Maps to**: Issue #1 (Strategy duplication)
**Steps**:
1. Navigate to `/strategy`
2. Wait for table

**Expected**:
- Page renders StrategyRecommend (3 tabs: 强势股/十倍潜力/突破)
- No 404 / no "Strategy" component-specific text

### TC-2.2 — /task-execution redirects to /task-center
**Maps to**: Issue #2 (TaskExecution + TaskResults merge)
**Steps**:
1. Navigate to `/task-execution`
2. Capture final URL after SPA hydration

**Expected**:
- URL is `/task-center`
- Title "任务中心" is visible

### TC-2.3 — /task-results redirects to /task-center
**Maps to**: Issue #2
**Steps**:
1. Navigate to `/task-results`
2. Capture final URL

**Expected**:
- URL is `/task-center`

### TC-2.4 — TaskCenter "执行状态" tab works
**Maps to**: Spec: `frontend-task-center`
**Steps**:
1. Navigate to `/task-center` (after redirect or direct)
2. Confirm "执行状态" tab is active by default
3. Wait for scheduler-status call

**Expected**:
- Scheduler status cards render (or empty state)
- "用户任务" sub-section present

### TC-2.5 — TaskCenter "执行结果" tab works
**Maps to**: Spec: `frontend-task-center`
**Steps**:
1. From `/task-center`, click "执行结果" tab
2. Date picker should be present

**Expected**:
- Tab switches
- Date picker renders with today as default
- Scheduler-runs table or empty state visible

### TC-2.6 — TaskCenter drawer detail
**Maps to**: Spec: drawer detail
**Steps**:
1. From TC-2.5 state, click a row in the scheduler-runs table

**Expected**:
- Drawer opens with task detail (状态/开始时间/结束时间/输出/错误)

---

## Round 3 — `frontend-final-optimizations`

### TC-3.1 — CommandPalette opens on ⌘K
**Maps to**: Issue #7 (CommandPalette enabled)
**Steps**:
1. Navigate to `/`
2. Press `Meta+k` (or `Control+k`)

**Expected**:
- Modal opens with input "输入命令或搜索..."
- Typing "task" shows 任务 / 任务中心 entries

### TC-3.2 — CommandPalette navigates on selection
**Maps to**: Issue #7
**Steps**:
1. From TC-3.1, type "watch"
2. Click first result

**Expected**:
- Modal closes
- URL becomes `/watchlist`

### TC-3.3 — Home and Watchlist share watchlist cache
**Maps to**: Issue #5 (useWatchlist)
**Steps**:
1. Navigate to `/watchlist?pageSize=20`
2. Wait for table to load
3. Navigate to `/` (Home)
4. Capture network requests

**Expected**:
- Home does **not** re-fetch `/api/watchlist?page=1&pageSize=12`
  when its pageSize matches cache
- Cache hit served from TanStack Query

### TC-3.4 — PaperAccounts shows TOP 3 card
**Maps to**: Issue #6
**Pre**: ≥3 paper accounts in DB
**Steps**:
1. Navigate to `/paper`
2. Wait for account grid

**Expected**:
- "收益排名 TOP 3" card is rendered above the grid
- Three medals 🥇🥈🥉 with account names and profit %
- "查看完整排名 →" link present

### TC-3.5 — PaperAccounts TOP 3 sorted by profit_pct
**Maps to**: Spec: `frontend-paper-top3`
**Steps**:
1. From TC-3.4 state, read the three profit values
2. Verify ordering

**Expected**:
- Three values in strictly descending order

### TC-3.6 — StockDetail initial load fires only always-on queries
**Maps to**: Issue #4
**Steps**:
1. Navigate to `/stock/000001`
2. Capture all `/api/...` calls before any tab click (5-second window)
3. Categorize each call

**Expected**:
- Fires: `realtime`, `comprehensive_with_indicators`, `sina/daily`,
  `with_benchmark` (chart tab default), watchlist position lookup
- Does **not** fire until tab activated: `fundamentals`, `analyst/predictions`,
  `stock/profile`, `sentiment/all`, `money_flow/history`, `risk/report`,
  `ml/predict`

### TC-3.7 — StockDetail fundamental tab triggers its queries
**Maps to**: Issue #4
**Steps**:
1. From TC-3.6 state, click "基本面" tab
2. Capture network

**Expected**:
- New calls to `/api/fundamentals/000001`, `/api/analyst/predictions/000001`,
  `/api/stock/profile/000001`

### TC-3.8 — StockDetail sentiment tab triggers its queries
**Maps to**: Issue #4
**Steps**:
1. From TC-3.6 state, click "舆情" tab
2. Capture network

**Expected**:
- New call to `/api/sentiment/all/000001`

---

## Cross-cutting

### TC-X.1 — Sidebar collapses task entries
**Maps to**: Sidebar consolidation (issue #2)
**Steps**:
1. Open any page
2. Read sidebar items

**Expected**:
- Sidebar shows **1** "任务中心" entry, not "任务执行" + "任务结果" separately

### TC-X.2 — No regression on existing pages
**Steps**:
1. Run smoke for all 25 pages

**Expected**:
- All 25 pages load with HTTP 200 and core elements present
- No new 5xx in API interception

---

## Acceptance criteria summary

| ID | Maps to optimization | Pass condition |
|----|----------------------|----------------|
| TC-1.1 | Watchlist dedup | 1 fetch per code (was 3) |
| TC-1.2 | Watchlist dedup | No duplicate fetches per tick |
| TC-1.3 | useRealtimeQuote guard | 0 fetches when empty |
| TC-2.1 | Strategy.tsx removed | /strategy still works |
| TC-2.2 | TaskCenter redirects | /task-execution → /task-center |
| TC-2.3 | TaskCenter redirects | /task-results → /task-center |
| TC-2.4 | TaskCenter status tab | Renders scheduler + user tasks |
| TC-2.5 | TaskCenter results tab | Date picker + historical runs |
| TC-2.6 | TaskCenter drawer | Row click opens detail |
| TC-3.1 | CommandPalette ⌘K | Modal opens |
| TC-3.2 | CommandPalette nav | Selection navigates |
| TC-3.3 | useWatchlist shared | No duplicate fetch Home→Watchlist |
| TC-3.4 | Paper TOP 3 card | Card visible when ≥3 accounts |
| TC-3.5 | Paper TOP 3 sorted | Descending profit_pct |
| TC-3.6 | StockDetail lazy | Only default-tab queries fire |
| TC-3.7 | StockDetail fundamental | Queries fire on tab click |
| TC-3.8 | StockDetail sentiment | Query fires on tab click |
| TC-X.1 | Sidebar consolidation | 1 task center entry |
| TC-X.2 | No regression | All pages still load |