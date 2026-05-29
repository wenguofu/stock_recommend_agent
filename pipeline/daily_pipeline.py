# pipeline/daily_pipeline.py
"""Daily post-close pipeline: data → features → DL training → screening → agent analysis → recommendations."""

import logging
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger('pipeline')


def run_daily_pipeline():
    """Execute the full daily pipeline. Called by scheduler after market close."""
    logger.info("=" * 60)
    logger.info(f"Daily pipeline started at {datetime.now()}")
    stage_times = {}

    try:
        # Stage 1: Data fetch
        t0 = datetime.now()
        logger.info("[1/6] Fetching post-close data...")
        stage_times['data_fetch'] = (datetime.now() - t0).total_seconds()

        # Stage 2: Feature engineering
        t0 = datetime.now()
        logger.info("[2/6] Running feature engineering...")
        stage_times['features'] = (datetime.now() - t0).total_seconds()

        # Stage 3: DL model training
        t0 = datetime.now()
        logger.info("[3/6] Training DL models...")
        stage_times['dl_training'] = (datetime.now() - t0).total_seconds()

        # Stage 4: Market-wide DL screening
        t0 = datetime.now()
        logger.info("[4/6] Running DL screening on all stocks...")
        candidates = _dl_screening()
        stage_times['dl_screening'] = (datetime.now() - t0).total_seconds()

        # Stage 5: LLM Agent analysis
        t0 = datetime.now()
        logger.info(f"[5/6] Running LLM agent analysis on top {len(candidates)} stocks...")
        recommendations = _agent_analysis(candidates[:30])
        stage_times['agent_analysis'] = (datetime.now() - t0).total_seconds()

        # Stage 6: Persist recommendations
        t0 = datetime.now()
        logger.info(f"[6/6] Saving {len(recommendations)} recommendations...")
        _save_recommendations(recommendations)
        stage_times['save'] = (datetime.now() - t0).total_seconds()

        logger.info("Daily pipeline complete!")
        for stage, duration in stage_times.items():
            logger.info(f"  {stage}: {duration:.1f}s")

        return {'success': True, 'stage_times': stage_times, 'recommendations': len(recommendations)}
    except Exception as e:
        logger.error(f"Daily pipeline failed: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}


def _dl_screening() -> list:
    """Run DL models on all stocks, return top candidates sorted by score."""
    logger.info("  DL screening — returns placeholder candidates")
    return []


def _agent_analysis(candidates: list) -> list:
    """Run LLM agent analysis on candidate stocks."""
    if not candidates:
        return []
    try:
        from llm_agents.agent_orchestrator import batch_analyze
        results = batch_analyze(candidates, max_concurrent=5)
        return results
    except ImportError:
        logger.warning("  LLM agents not available, skipping agent analysis")
        return []


def _save_recommendations(recommendations: list):
    """Save recommendations to DB."""
    from models import SessionLocal, Recommendation
    db = SessionLocal()
    try:
        for i, rec in enumerate(recommendations):
            decision = rec.get('decision', {})
            r = Recommendation(
                rec_type='daily',
                strategy='ai_hybrid',
                code=rec.get('code', ''),
                name=rec.get('name', ''),
                price=rec.get('price', 0),
                score=decision.get('confidence', 0),
                reason=decision.get('reasoning', ''),
                rank=i + 1,
            )
            db.add(r)
        db.commit()
        logger.info(f"  Saved {len(recommendations)} recommendations to DB")
    except Exception as e:
        db.rollback()
        logger.error(f"  Failed to save recommendations: {e}")
    finally:
        db.close()
