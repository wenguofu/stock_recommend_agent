## ADDED Requirements

### Requirement: Unified task center page
The system SHALL expose a single `/task-center` route rendering `TaskCenter.tsx`,
which consolidates current execution status and historical run results behind internal
tabs.

#### Scenario: User opens the unified page
- **WHEN** a user navigates to `/task-center`
- **THEN** the system SHALL render a tabbed interface with at least two tabs:
  one for "执行状态" (current scheduler + user-task status) and one for "执行结果"
  (historical runs by date).

#### Scenario: Old routes redirect to the unified page
- **WHEN** a user navigates to `/task-execution` or `/task-results`
- **THEN** the system SHALL redirect the browser to `/task-center` and render the
  unified page without loss of context.

### Requirement: Strategy.tsx deletion
The `Strategy.tsx` page component and its dedicated unit test SHALL be removed from
the codebase; the `/strategy` route continues to render `StrategyRecommend.tsx`,
which is the canonical implementation.

#### Scenario: Strategy.tsx is no longer in source tree
- **WHEN** the codebase is built
- **THEN** `Strategy.tsx` SHALL NOT be present under `src/pages/`.
- **WHEN** the test suite runs
- **THEN** `Strategy.test.tsx` SHALL NOT be present under `src/__tests__/`.

#### Scenario: /strategy route behavior preserved
- **WHEN** a user navigates to `/strategy`
- **THEN** the system SHALL render `StrategyRecommend.tsx` with the existing three-tab
  layout (强势股 / 十倍潜力 / 突破形态).