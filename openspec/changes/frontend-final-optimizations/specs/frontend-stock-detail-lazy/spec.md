## ADDED Requirements

### Requirement: StockDetail queries gated by active tab
The StockDetail page SHALL fetch tab-specific data only when the user activates that
tab. Always-on data (realtime, comprehensive, daily, watchlist for the position
banner) loads immediately.

#### Scenario: Initial mount fires only always-on queries
- **WHEN** the user navigates to a stock detail page
- **THEN** the system SHALL issue fetches only for `realtime`, `comprehensive`,
  `daily`, and the watchlist position query. Tab-specific queries
  (fundamental, sentiment, money-flow history, risk, ml, analyst, profile,
  with-benchmark) SHALL NOT fire until their tab is activated.

#### Scenario: Activating a tab fires its query
- **WHEN** the user clicks a tab that was not previously active
- **THEN** the system SHALL trigger that tab's fetcher exactly once.