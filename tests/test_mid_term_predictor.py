# tests/test_mid_term_predictor.py
import numpy as np
import torch
from dl_models.mid_term_predictor import MidTermPredictor, MidTermConfig

def test_mid_config():
    config = MidTermConfig()
    assert config.seq_len == 52
    assert config.d_model == 256
    assert config.num_heads == 8

def test_forward_pass():
    config = MidTermConfig(seq_len=52, num_price_features=8, num_fundamental_features=6)
    model = MidTermPredictor(config)
    x_price = torch.randn(4, 52, 8)
    x_fund = torch.randn(4, 6)
    regime = torch.tensor([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [1.0, 0.0, 0.0]])
    out = model(x_price, x_fund, regime)
    assert out['direction_logits'].shape == (4, 3)
    assert out['return_mu'].shape == (4, 1)
    assert out['return_sigma'].shape == (4, 1)

def test_predict_structure():
    np.random.seed(42)
    config = MidTermConfig(seq_len=52, num_price_features=8, num_fundamental_features=6)
    model = MidTermPredictor(config)
    price_features = np.random.randn(52, 8).astype(np.float32)
    fund_features = np.random.randn(6).astype(np.float32)
    result = model.predict(price_features, fund_features, regime_encoding=[1, 0, 0])
    assert result['direction'] in ['up', 'down', 'flat']
    assert result['horizon'] == '4w'
    assert 'expected_return' in result
    assert 'uncertainty' in result
    assert 'confidence_interval' in result
    assert 'key_drivers' in result
