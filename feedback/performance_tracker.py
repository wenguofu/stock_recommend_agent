# feedback/performance_tracker.py
"""Multi-dimension performance tracking for AI recommendations."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List
import numpy as np
from models import SessionLocal
from recommendation_tracker import RecommendationTrack, _wilson_ci

logger = logging.getLogger(__name__)


def compute_profit_factor(wins: List[float], losses: List[float]) -> float:
    """avg_win / |avg_loss|"""
    avg_win = np.mean(wins) if wins else 0
    avg_loss = abs(np.mean(losses)) if losses else 1e-10
    return round(avg_win / avg_loss, 2) if avg_loss > 0 else 0


def get_performance_report(days: int = 90) -> Dict:
    """Generate a comprehensive performance report across all signal sources."""
    db = SessionLocal()
    try:
        cutoff = datetime.now() - timedelta(days=days)
        tracks = (
            db.query(RecommendationTrack)
            .filter(
                RecommendationTrack.created_at >= cutoff,
                RecommendationTrack.status.in_(['hit', 'missed']),
                RecommendationTrack.result_hit.isnot(None),
            )
            .all()
        )

        if not tracks:
            return {'error': 'No evaluation data in period', 'days': days}

        # Group by source
        by_source = {}
        for t in tracks:
            src = t.source or 'unknown'
            if src not in by_source:
                by_source[src] = []
            by_source[src].append(t)

        source_reports = {}
        for src, src_tracks in by_source.items():
            hits = sum(1 for t in src_tracks if t.result_hit)
            total = len(src_tracks)
            win_rate = round(hits / total * 100, 1) if total > 0 else 0
            returns = [t.result_return_pct for t in src_tracks if t.result_return_pct is not None]
            wins = [r for r in returns if r > 0]
            losses = [r for r in returns if r < 0]
            profit_factor = compute_profit_factor(wins, losses)
            avg_return = round(np.mean(returns), 2) if returns else 0
            sharpe = round(np.mean(returns) / np.std(returns) * np.sqrt(252), 2) if len(returns) > 1 else 0
            max_dd = round(min(returns), 2) if returns else 0
            ci_low, ci_high = _wilson_ci(hits, total)

            source_reports[src] = {
                'total': total, 'hits': hits, 'win_rate': win_rate,
                'profit_factor': profit_factor, 'avg_return': avg_return,
                'sharpe': sharpe, 'max_drawdown': max_dd,
                'ci_95': f"{ci_low}%-{ci_high}%",
            }

        return {
            'period_days': days,
            'total_recommendations': len(tracks),
            'by_source': source_reports,
        }
    except Exception as e:
        logger.error(f"Performance report failed: {e}")
        return {'error': str(e)}
    finally:
        db.close()
