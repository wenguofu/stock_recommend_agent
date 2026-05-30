# Risk Control — 硬约束风控层

> Added: 2026-05-30

## Hard Constraints (risk_control/hard_constraints.py)

Pre-execution trade validation with 7 constraint checks:

| Constraint | Threshold | Action |
|------------|-----------|--------|
| Single position cap | ≤ 20% | Block/auto-reduce |
| Total exposure cap | ≤ 80% | Block buys, suggest reducing |
| Daily loss circuit breaker | -5% | No new positions, stop-loss only |
| Sector concentration | ≤ 30% | Block same-sector additions |
| Portfolio VaR limit | ≤ 2% of assets | Warning |
| Liquidity check | ≥ 50M CNY daily turnover | Exclude illiquid stocks |
| Stop-loss discipline | ATR 2x or -8% (tighter wins) | Auto-place stop order |

### API

`validate_order(action, target_code, target_sector, order_amount, portfolio_value, current_positions, ...)` → `ConstraintResult(passed, violations[], warnings[])`

### Circuit Breaker (risk_control/circuit_breaker.py)

- Reads daily P&L from `PaperSnapshot` DB table
- Trips when daily loss ≤ -5%
- Global singleton via `get_circuit_breaker()`
- Reset at start of new trading day

### Position Guard (risk_control/position_guard.py)

- `get_current_exposures(account_id)` → portfolio snapshot with sector breakdown
- `compute_max_order_size(account_id, code, sector)` → max allowed buy amount from 3 simultaneous constraints

### Integration

- Wired into `paper_trading.py create_order()` — called before every order
- Integrated into Midline position calculator — shows violation warnings
- Integrated into ValuationPanel — shows constraint-check result
