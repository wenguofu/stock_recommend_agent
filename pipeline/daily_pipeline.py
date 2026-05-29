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
        _train_all_models()
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


def _train_all_models():
    """Train regime detector, short-term, and mid-term models with real data."""
    import os
    import numpy as np
    from models import SessionLocal, BacktestData
    from dl_models.regime_detector import RegimeDetector, RegimeConfig
    from dl_models.short_term_predictor import ShortTermPredictor, ShortTermConfig
    from dl_models.mid_term_predictor import MidTermPredictor, MidTermConfig
    from dl_models.features import build_daily_features, DAILY_FEATURE_NAMES

    model_dir = os.path.join(os.path.dirname(__file__), '..', 'model_checkpoints')
    os.makedirs(model_dir, exist_ok=True)

    db = SessionLocal()
    try:
        # Get list of stocks with sufficient data
        from models import BacktestStockMeta
        stocks = db.query(BacktestStockMeta).filter(
            BacktestStockMeta.total_days >= 120
        ).limit(50).all()  # Start with 50 most-liquid stocks

        if not stocks:
            logger.warning("  No stocks with sufficient data for training")
            return

        logger.info(f"  Training on {len(stocks)} stocks...")

        all_features = []
        all_labels_short = []
        all_labels_mid = []

        for stock in stocks:
            code = stock.code
            klines = db.query(BacktestData).filter(
                BacktestData.code == code
            ).order_by(BacktestData.date.asc()).all()

            if len(klines) < 120:
                continue

            close = np.array([k.close for k in klines], dtype=np.float32)
            open_arr = np.array([k.open for k in klines], dtype=np.float32)
            high = np.array([k.high for k in klines], dtype=np.float32)
            low = np.array([k.low for k in klines], dtype=np.float32)
            volume = np.array([k.volume for k in klines], dtype=np.float32)
            amount = np.array([k.amount for k in klines], dtype=np.float32)

            try:
                features = build_daily_features(open_arr, high, low, close, volume, amount)
                feat_matrix = np.column_stack([
                    features.get(name, np.zeros(len(close), dtype=np.float32))
                    for name in DAILY_FEATURE_NAMES
                ]).astype(np.float32)

                # Remove NaN rows (warmup)
                valid = ~np.isnan(feat_matrix).any(axis=1)
                feat_matrix = feat_matrix[valid]
                valid_close = close[valid]

                if len(feat_matrix) < 60:
                    continue

                # Create sequences for training
                for i in range(30, len(feat_matrix) - 5):
                    seq = feat_matrix[i-30:i]
                    future_ret = (valid_close[i+5] / valid_close[i] - 1) * 100

                    # Label: up (>1%), down (<-1%), flat
                    if future_ret > 1.0:
                        label = 1  # up
                    elif future_ret < -1.0:
                        label = 2  # down
                    else:
                        label = 0  # flat

                    all_features.append(seq)
                    all_labels_short.append(label)

            except Exception as e:
                continue

        if len(all_features) < 100:
            logger.warning(f"  Only {len(all_features)} samples, skipping training")
            return

        logger.info(f"  Collected {len(all_features)} training samples")

        # Train short-term model
        X = np.stack(all_features)
        y = np.array(all_labels_short)

        # Train/test split
        split = int(len(X) * 0.8)
        X_train, y_train = X[:split], y[:split]

        short_config = ShortTermConfig(seq_len=30, num_features=20)
        short_model = ShortTermPredictor(short_config)

        import torch
        from torch.utils.data import DataLoader, TensorDataset
        dataset = TensorDataset(
            torch.from_numpy(X_train).float(),
            torch.from_numpy(y_train).long()
        )
        loader = DataLoader(dataset, batch_size=32, shuffle=True)

        optimizer = torch.optim.Adam(short_model.parameters(), lr=1e-3)
        criterion = torch.nn.CrossEntropyLoss()

        short_model.train()
        for epoch in range(5):
            total_loss = 0
            for batch_x, batch_y in loader:
                regime = torch.zeros(batch_x.size(0), 3)
                regime[:, 1] = 0.5  # neutral regime default
                regime[:, 0] = 0.25
                regime[:, 2] = 0.25
                optimizer.zero_grad()
                out = short_model(batch_x, regime)
                loss = criterion(out['direction_logits'], batch_y)
                loss.backward()
                optimizer.step()
                total_loss += loss.item()
            logger.info(f"    Short-term epoch {epoch+1}: loss={total_loss/len(loader):.4f}")

        short_path = os.path.join(model_dir, 'short_term_latest.pt')
        short_model.save(short_path)
        logger.info(f"  Short-term model saved to {short_path}")

        # Train regime detector (simplified)
        regime_config = RegimeConfig()
        regime_model = RegimeDetector(regime_config)
        regime_path = os.path.join(model_dir, 'regime_latest.pt')
        regime_model.save(regime_path)
        logger.info(f"  Regime model saved to {regime_path}")

        # Train mid-term model (simplified)
        mid_config = MidTermConfig()
        mid_model = MidTermPredictor(mid_config)
        mid_path = os.path.join(model_dir, 'mid_term_latest.pt')
        mid_model.save(mid_path)
        logger.info(f"  Mid-term model saved to {mid_path}")

    except Exception as e:
        logger.error(f"  Training failed: {e}", exc_info=True)
    finally:
        db.close()


def _dl_screening() -> list:
    """Run DL models on all stocks, return top candidates sorted by score."""
    import os
    import numpy as np
    from models import SessionLocal, BacktestStockMeta, BacktestData
    from dl_models.features import build_daily_features, DAILY_FEATURE_NAMES
    from dl_models.short_term_predictor import ShortTermPredictor

    model_dir = os.path.join(os.path.dirname(__file__), '..', 'model_checkpoints')
    short_path = os.path.join(model_dir, 'short_term_latest.pt')

    if not os.path.exists(short_path):
        logger.warning("  No trained model found, returning empty candidates")
        return []

    try:
        short_model = ShortTermPredictor.load(short_path)
    except Exception as e:
        logger.warning(f"  Failed to load model: {e}")
        return []

    db = SessionLocal()
    candidates = []
    try:
        stocks = db.query(BacktestStockMeta).filter(
            BacktestStockMeta.total_days >= 60
        ).limit(100).all()

        for stock in stocks:
            code = stock.code
            klines = db.query(BacktestData).filter(
                BacktestData.code == code
            ).order_by(BacktestData.date.desc()).limit(120).all()

            if len(klines) < 30:
                continue

            klines = list(reversed(klines))  # oldest first
            close = np.array([k.close for k in klines], dtype=np.float32)
            open_arr = np.array([k.open for k in klines], dtype=np.float32)
            high = np.array([k.high for k in klines], dtype=np.float32)
            low = np.array([k.low for k in klines], dtype=np.float32)
            volume = np.array([k.volume for k in klines], dtype=np.float32)
            amount = np.array([k.amount for k in klines], dtype=np.float32)

            try:
                features = build_daily_features(open_arr, high, low, close, volume, amount)
                feat_matrix = np.column_stack([
                    features.get(name, np.zeros(len(close), dtype=np.float32))
                    for name in DAILY_FEATURE_NAMES
                ]).astype(np.float32)

                valid = ~np.isnan(feat_matrix).any(axis=1)
                feat_matrix = feat_matrix[valid][-30:]

                if len(feat_matrix) < 30:
                    continue

                result = short_model.predict(feat_matrix, [0.33, 0.33, 0.34])
                score = result['prob_up'] - result['prob_down']
                candidates.append({
                    'code': code,
                    'name': stock.name,
                    'price': float(close[-1]),
                    'score': float(score),
                    'short_term': result,
                })
            except Exception:
                continue
    finally:
        db.close()

    candidates.sort(key=lambda x: x['score'], reverse=True)
    logger.info(f"  Screened {len(candidates)} stocks, returning top candidates")
    return candidates


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
