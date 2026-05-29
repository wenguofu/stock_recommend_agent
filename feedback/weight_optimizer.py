# feedback/weight_optimizer.py
"""Auto-tuning engine — adjusts signal fusion weights based on tracked performance."""

import logging
from typing import Dict

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS = {
    'debate': 0.25,
    'factor': 0.20,
    'money_flow': 0.15,
    'technical': 0.15,
    'sector': 0.10,
    'risk': 0.15,
}

MIN_WEIGHT = 0.05
MAX_WEIGHT = 0.40


def tune_weights(performance_report: Dict, current_weights: Dict = None) -> Dict:
    """
    Adjust weights based on recent performance.
    Sources performing better get weight increases, underperformers get reduced.
    Rules: Win rate > 60% → +5%, < 45% → -5%, Profit factor > 1.5 → bonus +3%
    """
    if current_weights is None:
        current_weights = dict(DEFAULT_WEIGHTS)

    by_source = performance_report.get('by_source', {})
    if not by_source:
        return current_weights

    adjustments = {}
    for src, report in by_source.items():
        if src not in current_weights:
            continue
        adj = 0
        wr = report.get('win_rate', 50)
        pf = report.get('profit_factor', 1.0)

        if wr > 60:
            adj += 0.05
        elif wr < 45:
            adj -= 0.05
        if pf > 1.5:
            adj += 0.03
        if pf < 0.8:
            adj -= 0.03

        adjustments[src] = adj

    new_weights = {}
    for src, w in current_weights.items():
        new_w = w + adjustments.get(src, 0)
        new_weights[src] = max(MIN_WEIGHT, min(MAX_WEIGHT, new_w))

    # Normalize to sum to 1.0
    total = sum(new_weights.values())
    if total > 0:
        new_weights = {k: round(v / total, 4) for k, v in new_weights.items()}

    logger.info(f"Weight tuning: {adjustments} -> {new_weights}")
    return new_weights
