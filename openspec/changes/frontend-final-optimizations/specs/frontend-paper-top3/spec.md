## ADDED Requirements

### Requirement: Top-3 ranking snippet in PaperAccounts
The PaperAccounts page SHALL display a compact "收益排名 TOP 3" card showing the
three highest-yielding accounts.

#### Scenario: Top-3 sorted by total_profit_pct
- **WHEN** the PaperAccounts page renders and at least three accounts exist
- **THEN** the top-3 card SHALL show the three accounts with the highest
  `total_profit_pct` value, in descending order.