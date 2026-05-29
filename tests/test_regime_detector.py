# tests/test_regime_detector.py
import numpy as np
import torch
import pytest
from dl_models.regime_detector import RegimeDetector, RegimeConfig

@pytest.fixture
def sample_data():
    """Generate synthetic market data with known regimes."""
    np.random.seed(42)
    n = 200
    # Bull: rising prices, high breadth, positive north flow
    bull_close = 100 + np.cumsum(np.random.randn(n//3) * 0.3 + 0.15)
    bull_vol = np.random.rand(n//3) * 1e9 + 5e8
    bull_breadth = np.random.rand(n//3) * 0.2 + 0.6

    # Bear: falling prices, low breadth
    bear_close = np.full(n//3, np.nan)
    bear_close[0] = bull_close[-1]
    for i in range(1, n//3):
        bear_close[i] = bear_close[i-1] + np.random.randn() * 0.3 - 0.12
    bear_breadth = np.random.rand(n//3) * 0.3 + 0.1

    # Sideways: flat prices
    side_close = np.full(n//3, np.nan)
    side_close[0] = bear_close[-1]
    for i in range(1, n//3):
        side_close[i] = side_close[i-1] + np.random.randn() * 0.2
    side_breadth = np.random.rand(n//3) * 0.3 + 0.35

    close = np.concatenate([bull_close, bear_close, side_close]).astype(np.float32)
    volume = np.concatenate([bull_vol, bear_close * 1e7 + 5e8, bear_close * 1e7 + 5e8]).astype(np.float32)
    breadth = np.concatenate([bull_breadth, bear_breadth, side_breadth]).astype(np.float32)

    return close, volume, breadth

def test_regime_config():
    config = RegimeConfig()
    assert config.num_regimes == 3
    assert config.d_model == 128
    assert config.num_heads == 4

def test_regime_detector_build(sample_data):
    """Smoke test: model builds and forward pass works."""
    close, volume, breadth = sample_data
    config = RegimeConfig(seq_len=60)
    model = RegimeDetector(config)

    x = np.column_stack([close, volume, breadth]).astype(np.float32)
    x_tensor = torch.from_numpy(x[-60:]).unsqueeze(0)  # (1, 60, 3)

    with torch.no_grad():
        output = model(x_tensor)

    assert output['logits'].shape == (1, 3)
    assert output['probs'].shape == (1, 3)
    assert torch.allclose(output['probs'].sum(), torch.tensor(1.0), atol=0.01)

def test_regime_detector_predict_structure(sample_data):
    """Test the predict() method returns correct dict structure."""
    close, volume, breadth = sample_data
    config = RegimeConfig(seq_len=60)
    model = RegimeDetector(config)

    x = np.column_stack([close, volume, breadth]).astype(np.float32)
    result = model.predict(x[-60:])

    assert 'regime' in result
    assert result['regime'] in ['bull', 'bear', 'sideways']
    assert 'confidence' in result
    assert 0 <= result['confidence'] <= 1
    assert 'probabilities' in result
    assert set(result['probabilities'].keys()) == {'bull', 'bear', 'sideways'}
    assert 'regime_score' in result
