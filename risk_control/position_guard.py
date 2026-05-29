# risk_control/position_guard.py
"""Position size and sector concentration guard."""

import logging
from typing import Dict, List, Optional
from models import SessionLocal, PaperPosition, PaperAccount

logger = logging.getLogger(__name__)

def get_current_exposures(account_id: int) -> dict:
    """Get current portfolio exposure metrics for an account."""
    db = SessionLocal()
    try:
        account = db.query(PaperAccount).filter(PaperAccount.id == account_id).first()
        if not account:
            return {}

        positions = db.query(PaperPosition).filter(
            PaperPosition.account_id == account_id
        ).all()

        pos_list = []
        sector_map = {}
        total_mv = 0

        for p in positions:
            mv = p.market_value or 0
            pos_list.append({
                'code': p.code,
                'name': p.name,
                'market_value': mv,
                'profit_pct': p.profit_pct,
            })
            total_mv += mv

            sector = _code_to_sector(p.code)
            sector_map[sector] = sector_map.get(sector, 0) + mv

        portfolio_value = (account.cash_balance or 0) + total_mv

        return {
            'portfolio_value': portfolio_value,
            'cash': account.cash_balance or 0,
            'total_market_value': total_mv,
            'exposure_pct': round(total_mv / portfolio_value * 100, 1) if portfolio_value > 0 else 0,
            'positions': pos_list,
            'sector_exposure': {s: round(v / portfolio_value * 100, 1) if portfolio_value > 0 else 0
                               for s, v in sector_map.items()},
        }
    except Exception as e:
        logger.error(f"get_current_exposures failed: {e}")
        return {}
    finally:
        db.close()

def _code_to_sector(code: str) -> str:
    """Map stock code prefix to sector name."""
    prefix = code[:2]
    mapping = {
        '60': 'Shanghai Main', '68': 'STAR',
        '00': 'Shenzhen Main', '30': 'ChiNext',
        '83': 'Beijing', '43': 'Beijing', '87': 'Beijing',
        '15': 'ETF', '51': 'ETF', '56': 'ETF', '58': 'ETF',
    }
    return mapping.get(prefix, 'Other')

def compute_max_order_size(account_id: int, code: str, sector: str = None,
                            max_single_pct: float = 20,
                            max_sector_pct: float = 30,
                            max_total_pct: float = 80) -> Optional[float]:
    """Compute the maximum allowed order amount for a buy order."""
    exposures = get_current_exposures(account_id)
    if not exposures:
        return None

    pv = exposures['portfolio_value']
    total_mv = exposures['total_market_value']

    # Constraint 1: total exposure limit
    max_from_total = pv * (max_total_pct / 100) - total_mv

    # Constraint 2: single position limit
    existing = next((p for p in exposures['positions'] if p['code'] == code), None)
    existing_mv = existing['market_value'] if existing else 0
    max_from_single = pv * (max_single_pct / 100) - existing_mv

    # Constraint 3: sector limit
    max_from_sector = float('inf')
    if sector:
        sector_key = _code_to_sector(code)
        sector_pct = exposures.get('sector_exposure', {}).get(sector_key, 0)
        sector_mv = sector_pct / 100 * pv if sector_pct else 0
        max_from_sector = pv * (max_sector_pct / 100) - sector_mv

    max_order = min(max_from_total, max_from_single, max_from_sector)
    return max(0, round(max_order, 2))
