# risk_control/hard_constraints.py
"""Pre-execution hard constraint validator. All constraints must pass before order."""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

@dataclass
class ConstraintConfig:
    single_position_max_pct: float = 20.0
    total_exposure_max_pct: float = 80.0
    daily_loss_circuit_breaker_pct: float = 5.0
    sector_concentration_max_pct: float = 30.0
    portfolio_var_max_pct: float = 2.0
    min_daily_turnover_cny: float = 50_000_000
    atr_stop_multiplier: float = 2.0
    hard_stop_loss_pct: float = 8.0

@dataclass
class ConstraintResult:
    passed: bool
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

def validate_order(
    action: str,
    target_code: str,
    target_sector: str,
    order_amount: float,
    portfolio_value: float,
    current_positions: List[Dict],
    current_daily_pnl_pct: float = 0,
    sector_exposure_map: Dict[str, float] = None,
    portfolio_var: float = None,
    avg_daily_turnover: float = None,
    config: ConstraintConfig = None,
) -> ConstraintResult:
    """Validate a proposed order against all hard constraints."""
    if config is None:
        config = ConstraintConfig()
    violations = []
    warnings = []

    # 1. Daily loss circuit breaker
    if current_daily_pnl_pct <= -config.daily_loss_circuit_breaker_pct:
        if action == 'buy':
            violations.append(
                f"Daily loss circuit breaker triggered: {current_daily_pnl_pct:.1f}% <= "
                f"-{config.daily_loss_circuit_breaker_pct}%. No new buys allowed."
            )

    # 2. Total exposure check (for buy orders)
    total_market_value = sum(p.get('market_value', 0) for p in current_positions)
    new_exposure_pct = ((total_market_value + order_amount) / portfolio_value) * 100 if portfolio_value > 0 else 0

    if action == 'buy' and new_exposure_pct > config.total_exposure_max_pct:
        violations.append(
            f"Total exposure would be {new_exposure_pct:.1f}% (limit: {config.total_exposure_max_pct}%). "
            f"Reduce existing positions first."
        )

    # 3. Single position cap
    if action == 'buy':
        existing_position = next((p for p in current_positions if p.get('code') == target_code), None)
        existing_value = existing_position.get('market_value', 0) if existing_position else 0
        new_single_pct = ((existing_value + order_amount) / portfolio_value) * 100 if portfolio_value > 0 else 0
        if new_single_pct > config.single_position_max_pct:
            violations.append(
                f"Single position would be {new_single_pct:.1f}% (limit: {config.single_position_max_pct}%). "
                f"Reduce order size."
            )

    # 4. Sector concentration
    if action == 'buy' and sector_exposure_map and target_sector:
        sector_value = sector_exposure_map.get(target_sector, 0) + order_amount
        sector_pct = (sector_value / portfolio_value) * 100 if portfolio_value > 0 else 0
        if sector_pct > config.sector_concentration_max_pct:
            violations.append(
                f"Sector '{target_sector}' concentration would be {sector_pct:.1f}% "
                f"(limit: {config.sector_concentration_max_pct}%)."
            )

    # 5. Portfolio VaR limit
    if portfolio_var is not None and portfolio_value > 0:
        var_pct = (portfolio_var / portfolio_value) * 100
        if var_pct > config.portfolio_var_max_pct:
            warnings.append(f"Portfolio VaR at {var_pct:.1f}% exceeds limit {config.portfolio_var_max_pct}%")

    # 6. Liquidity check
    if avg_daily_turnover is not None and avg_daily_turnover < config.min_daily_turnover_cny:
        violations.append(
            f"Insufficient liquidity: avg daily turnover {avg_daily_turnover:,.0f} CNY "
            f"(min: {config.min_daily_turnover_cny:,.0f} CNY)"
        )

    return ConstraintResult(
        passed=len(violations) == 0,
        violations=violations,
        warnings=warnings,
    )

def compute_stop_loss(current_price: float, atr: float = None,
                       config: ConstraintConfig = None) -> Tuple[float, str]:
    """Compute stop-loss price using tighter of ATR 2x or -8%."""
    if config is None:
        config = ConstraintConfig()
    atr_stop = current_price * (1 - atr * config.atr_stop_multiplier / current_price) if atr else None
    pct_stop = current_price * (1 - config.hard_stop_loss_pct / 100)
    if atr_stop is not None and atr_stop > pct_stop:
        return round(atr_stop, 2), 'ATR'
    return round(pct_stop, 2), 'fixed_pct'
