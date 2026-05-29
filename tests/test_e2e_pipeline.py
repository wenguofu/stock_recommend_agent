# tests/test_e2e_pipeline.py
"""End-to-end smoke tests for the AI trading pipeline."""

import pytest
import numpy as np

class TestE2EPipeline:
    def test_feature_to_prediction_flow(self):
        """Smoke test: features -> model -> prediction output."""
        from dl_models.features import build_daily_features, DAILY_FEATURE_NAMES
        from dl_models.short_term_predictor import ShortTermPredictor, ShortTermConfig

        n = 60
        np.random.seed(42)
        close = 100 + np.cumsum(np.random.randn(n) * 0.5)
        open_a = close - np.random.rand(n) * 0.3
        high = close + np.abs(np.random.randn(n)) * 0.5
        low = close - np.abs(np.random.randn(n)) * 0.5
        volume = np.random.rand(n) * 1e7 + 5e6
        amount = volume * close

        feat_dict = build_daily_features(open_a, high, low, close, volume, amount)
        feat_matrix = np.column_stack([
            feat_dict.get(name, np.zeros(n)) for name in DAILY_FEATURE_NAMES
        ]).astype(np.float32)

        valid = ~np.isnan(feat_matrix).any(axis=1)
        feat_matrix = feat_matrix[valid][-30:]

        config = ShortTermConfig(seq_len=30, num_features=20)
        model = ShortTermPredictor(config)
        result = model.predict(feat_matrix, [1, 0, 0])

        assert result['direction'] in ['up', 'down', 'flat']
        assert abs(result['prob_up'] + result['prob_down'] + result['prob_flat'] - 1.0) < 0.01
        assert 'expected_return' in result
        assert 'confidence_interval' in result

    def test_hard_constraint_validation(self):
        """Test that hard constraint validator catches violations."""
        from risk_control.hard_constraints import validate_order, ConstraintConfig

        config = ConstraintConfig(single_position_max_pct=20, total_exposure_max_pct=80)
        positions = [
            {'code': '000001', 'market_value': 70000, 'sector': 'Banks'},
            {'code': '600519', 'market_value': 50000, 'sector': 'Liquor'},
        ]
        result = validate_order(
            action='buy', target_code='000001', target_sector='Banks',
            order_amount=40000, portfolio_value=100000,
            current_positions=positions,
            sector_exposure_map={'Banks': 70000, 'Liquor': 50000},
        )
        assert not result.passed
        assert any('Single position' in v for v in result.violations)

    def test_circuit_breaker_logic(self):
        """Test circuit breaker recognizes excessive loss."""
        from risk_control.hard_constraints import validate_order
        result = validate_order(
            action='buy', target_code='000001', target_sector='Banks',
            order_amount=5000, portfolio_value=100000,
            current_positions=[], current_daily_pnl_pct=-6.0,
        )
        assert not result.passed
        assert any('circuit breaker' in v.lower() for v in result.violations)
