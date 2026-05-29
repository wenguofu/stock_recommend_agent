# risk_control/circuit_breaker.py
"""Daily loss circuit breaker — blocks new trades when daily loss exceeds threshold."""

import logging
from datetime import date
from models import SessionLocal, PaperSnapshot

logger = logging.getLogger(__name__)

class CircuitBreaker:
    """Tracks daily P&L and enforces circuit breaker rules."""

    def __init__(self, threshold_pct: float = 5.0):
        self.threshold_pct = threshold_pct
        self._tripped_accounts = set()

    def check(self, account_id: int) -> dict:
        """Check if circuit breaker is tripped for an account."""
        db = SessionLocal()
        try:
            today = date.today().isoformat()
            latest_snap = (
                db.query(PaperSnapshot)
                .filter(
                    PaperSnapshot.account_id == account_id,
                    PaperSnapshot.snapshot_time >= today,
                )
                .order_by(PaperSnapshot.snapshot_time.desc())
                .first()
            )

            if not latest_snap:
                return {'tripped': False, 'daily_pnl_pct': 0, 'reason': ''}

            daily_pnl = latest_snap.daily_pnl_pct or 0

            if daily_pnl <= -self.threshold_pct:
                self._tripped_accounts.add(account_id)
                return {
                    'tripped': True,
                    'daily_pnl_pct': round(daily_pnl, 2),
                    'reason': f'Daily loss {daily_pnl:.1f}% exceeded circuit breaker threshold {self.threshold_pct}%',
                }

            return {'tripped': False, 'daily_pnl_pct': round(daily_pnl, 2), 'reason': ''}
        except Exception as e:
            logger.error(f"Circuit breaker check failed: {e}")
            return {'tripped': False, 'daily_pnl_pct': 0, 'reason': f'Error: {e}'}
        finally:
            db.close()

    def reset(self, account_id: int = None):
        """Reset circuit breaker (called at start of new trading day)."""
        if account_id:
            self._tripped_accounts.discard(account_id)
        else:
            self._tripped_accounts.clear()


# Global instance
_cb = CircuitBreaker()

def get_circuit_breaker() -> CircuitBreaker:
    return _cb
