"""Short-term stock predictor — BiLSTM + MultiHeadAttention (1-5 day horizon)."""

import numpy as np
import torch
import pytest
from dl_models.short_term_predictor import ShortTermPredictor, ShortTermConfig

def test_short_config():
    config = ShortTermConfig()
    assert config.seq_len == 30
    assert config.hidden_dim == 128
    assert config.num_layers == 2

def test_forward_pass():
    config = ShortTermConfig(seq_len=30, num_features=20)
    model = ShortTermPredictor(config)
    x = torch.randn(4, 30, 20)  # (batch=4, seq_len=30, features=20)
    # one-hot regime encoding: (B, 3) — bull, bear, sideways
    regime = torch.tensor([[1, 0, 0], [0, 1, 0], [0, 0, 1], [0.5, 0.5, 0.0]])
    out = model(x, regime)
    assert out['direction_logits'].shape == (4, 3)
    assert out['return_mu'].shape == (4, 1)
    assert out['return_sigma'].shape == (4, 1)
    assert out['direction_probs'].shape == (4, 3)
    # sigma must be positive
    assert (out['return_sigma'] > 0).all()

def test_predict_structure():
    np.random.seed(42)
    config = ShortTermConfig(seq_len=30, num_features=20)
    model = ShortTermPredictor(config)
    features = np.random.randn(30, 20).astype(np.float32)
    result = model.predict(features, regime_encoding=[1, 0, 0])
    assert result['direction'] in ['up', 'down', 'flat']
    assert 'prob_up' in result
    assert 'prob_down' in result
    assert 'prob_flat' in result
    assert 'expected_return' in result
    assert 'uncertainty' in result
    assert 'confidence_interval' in result
    assert len(result['confidence_interval']) == 2
    assert 'key_drivers' in result
