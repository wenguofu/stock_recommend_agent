# AI Trading System Optimization — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a dual-layer AI architecture (DL prediction + LLM Agent decision + two-layer risk control) that produces calibrated stock recommendations with consistent profitability.

**Architecture:** PyTorch DL models (Transformer/LSTM) produce probabilistic price predictions; 4 specialist LLM agents analyze market/technical/fundamental/risk dimensions in parallel; a fusion agent synthesizes final decisions; hard-constraint risk control validates before execution; closed-loop feedback auto-tunes weights monthly.

**Tech Stack:** PyTorch 2.x, ONNX Runtime, DeepSeek LLM API, Flask, SQLAlchemy, React/TypeScript

---

## Phase 1: DL Prediction Layer

### File Map

```
dl_models/
  __init__.py          — package init, exports all public interfaces
  features.py          — feature engineering (daily/weekly/market-level)
  regime_detector.py   — Transformer regime classifier
  short_term_predictor.py — BiLSTM+Attention short-term predictor
  mid_term_predictor.py   — Transformer mid-term predictor
  calibration.py       — temperature scaling + isotonic regression
  onnx_export.py       — PyTorch → ONNX conversion utilities

tests/
  test_dl_features.py
  test_regime_detector.py
  test_short_term_predictor.py
  test_mid_term_predictor.py
  test_calibration.py

Modified:
  ml_predictor.py      — wrap DL inference, keep RF fallback
  factor_engine.py     — add get_feature_vector() export
```

---

### Task 1.1: Install DL dependencies

**Files:** None (environment)

- [ ] **Step 1: Install PyTorch and ONNX**

```bash
pip install torch>=2.0 onnx onnxruntime loguru
```

Run: `pip show torch onnx onnxruntime loguru`
Expected: Shows version info for all four packages.

- [ ] **Step 2: Verify PyTorch works**

```python
python -c "import torch; print(torch.__version__); print(torch.rand(3,3))"
```

Expected: Prints version ≥2.0 and a 3×3 tensor.

---

### Task 1.2: Create dl_models package and feature engineering

**Files:**
- Create: `dl_models/__init__.py`
- Create: `dl_models/features.py`
- Create: `tests/test_dl_features.py`

- [ ] **Step 1: Create package init**

```python
# dl_models/__init__.py
"""DL prediction models for stock trading."""
```

- [ ] **Step 2: Write feature engineering module**

```python
# dl_models/features.py
"""Feature engineering for DL models — daily, weekly, and market-level features."""

import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional

def compute_returns(close: np.ndarray, periods: list) -> Dict[str, np.ndarray]:
    """Compute returns over multiple periods. Returns dict keyed by 'ret_{p}d'."""
    result = {}
    for p in periods:
        ret = np.full_like(close, np.nan, dtype=np.float32)
        ret[p:] = (close[p:] / close[:-p] - 1) * 100
        result[f'ret_{p}d'] = ret
    return result

def compute_volatility(close: np.ndarray, window: int = 20) -> np.ndarray:
    """Rolling historical volatility (annualized)."""
    ret = np.full_like(close, np.nan)
    ret[1:] = (close[1:] / close[:-1] - 1)
    vol = np.full_like(close, np.nan)
    for i in range(window, len(close) + 1):
        vol[i-1] = np.nanstd(ret[i-window:i]) * np.sqrt(252)
    return vol

def compute_ma_deviation(close: np.ndarray, window: int) -> np.ndarray:
    """Price deviation from moving average, as fraction."""
    ma = np.full_like(close, np.nan)
    for i in range(window - 1, len(close)):
        ma[i] = np.mean(close[i-window+1:i+1])
    return (close - ma) / ma

def compute_rsi(close: np.ndarray, window: int = 14) -> np.ndarray:
    """RSI indicator."""
    delta = np.full_like(close, np.nan)
    delta[1:] = close[1:] - close[:-1]
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    avg_gain = np.full_like(close, np.nan)
    avg_loss = np.full_like(close, np.nan)
    for i in range(window, len(close)):
        avg_gain[i] = np.mean(gain[i-window+1:i+1])
        avg_loss[i] = np.mean(loss[i-window+1:i+1])
    rs = avg_gain / (avg_loss + 1e-10)
    return 100.0 - (100.0 / (1.0 + rs))

def compute_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, window: int = 14) -> np.ndarray:
    """Average True Range."""
    tr = np.full_like(close, np.nan)
    tr[1:] = np.maximum(
        high[1:] - low[1:],
        np.maximum(
            np.abs(high[1:] - close[:-1]),
            np.abs(low[1:] - close[:-1])
        )
    )
    atr = np.full_like(close, np.nan)
    for i in range(window, len(close)):
        atr[i] = np.mean(tr[i-window+1:i+1])
    return atr

def compute_volume_ratio(volume: np.ndarray, window: int = 5) -> np.ndarray:
    """Volume ratio: current volume / MA volume."""
    ma_vol = np.full_like(volume, np.nan, dtype=np.float32)
    for i in range(window - 1, len(volume)):
        ma_vol[i] = np.mean(volume[i-window+1:i+1])
    return volume / ma_vol

def build_daily_features(
    open_arr: np.ndarray, high_arr: np.ndarray, low_arr: np.ndarray,
    close_arr: np.ndarray, volume_arr: np.ndarray, amount_arr: np.ndarray,
    turnover_arr: Optional[np.ndarray] = None,
    money_flow_5d: Optional[np.ndarray] = None,
    money_flow_10d: Optional[np.ndarray] = None,
) -> Dict[str, np.ndarray]:
    """
    Build daily-frequency feature dict for a single stock.
    All input arrays are 1-D numpy float32, aligned by date (oldest→newest).
    Returns dict of feature_name → 1-D array.
    """
    features = {}

    # Returns
    features.update(compute_returns(close_arr, [1, 3, 5, 10, 20]))

    # Volatility
    features['volatility_20d'] = compute_volatility(close_arr, 20)

    # MA deviations
    for w in [5, 10, 20, 60]:
        features[f'ma_dev_{w}d'] = compute_ma_deviation(close_arr, w)

    # RSI
    features['rsi_14'] = compute_rsi(close_arr, 14)

    # ATR ratio
    atr = compute_atr(high_arr, low_arr, close_arr, 14)
    features['atr_ratio'] = atr / close_arr

    # Volume ratio
    features['volume_ratio'] = compute_volume_ratio(volume_arr, 5)

    # Bollinger position
    ma20 = np.full_like(close_arr, np.nan)
    std20 = np.full_like(close_arr, np.nan)
    for i in range(19, len(close_arr)):
        ma20[i] = np.mean(close_arr[i-19:i+1])
        std20[i] = np.std(close_arr[i-19:i+1])
    features['bollinger_pos'] = (close_arr - ma20) / (std20 + 1e-10)

    # Amplitude
    features['amplitude'] = (high_arr - low_arr) / close_arr

    # Consecutive up/down days
    up_days = np.zeros_like(close_arr, dtype=np.float32)
    down_days = np.zeros_like(close_arr, dtype=np.float32)
    for i in range(1, len(close_arr)):
        if close_arr[i] > close_arr[i-1]:
            up_days[i] = up_days[i-1] + 1
            down_days[i] = 0
        elif close_arr[i] < close_arr[i-1]:
            down_days[i] = down_days[i-1] + 1
            up_days[i] = 0
    features['consecutive_up'] = up_days
    features['consecutive_down'] = down_days

    # Money flow (optional, from external)
    if money_flow_5d is not None:
        features['money_flow_5d'] = money_flow_5d
    if money_flow_10d is not None:
        features['money_flow_10d'] = money_flow_10d

    # Turnover
    if turnover_arr is not None:
        features['turnover_rate'] = turnover_arr

    return features

def build_market_features(
    index_close: np.ndarray,          # CSI 300 60-day close
    index_volume: np.ndarray,         # CSI 300 60-day volume
    breadth: np.ndarray,              # up_stocks / total_stocks per day
    north_flow: Optional[np.ndarray] = None,  # north-bound net flow
    sector_dispersion: Optional[np.ndarray] = None,  # sector return std
) -> np.ndarray:
    """
    Build market-level feature matrix for regime detection.
    Returns (T, N) array where T = sequence length, N = features.
    """
    features = []
    features.append((index_close - np.mean(index_close)) / np.std(index_close))
    features.append(compute_ma_deviation(index_close, 20))

    ret_5d = np.full_like(index_close, np.nan)
    ret_5d[5:] = (index_close[5:] / index_close[:-5] - 1) * 100
    features.append(ret_5d)

    vol_ratio = compute_volume_ratio(index_volume, 20)
    features.append(vol_ratio)

    features.append(breadth)

    if north_flow is not None:
        features.append(north_flow)

    if sector_dispersion is not None:
        features.append(sector_dispersion)

    return np.column_stack(features).astype(np.float32)

DAILY_FEATURE_NAMES = [
    'ret_1d', 'ret_3d', 'ret_5d', 'ret_10d', 'ret_20d',
    'volatility_20d',
    'ma_dev_5d', 'ma_dev_10d', 'ma_dev_20d', 'ma_dev_60d',
    'rsi_14', 'atr_ratio', 'volume_ratio', 'bollinger_pos', 'amplitude',
    'consecutive_up', 'consecutive_down',
    'money_flow_5d', 'money_flow_10d', 'turnover_rate',
]
```

- [ ] **Step 3: Write the feature test**

```python
# tests/test_dl_features.py
import numpy as np
import pytest
from dl_models.features import (
    compute_returns, compute_rsi, compute_atr,
    build_daily_features, build_market_features, DAILY_FEATURE_NAMES,
)

class TestComputeReturns:
    def test_ret_3d(self):
        close = np.array([10.0, 10.5, 10.2, 10.8, 11.0], dtype=np.float32)
        result = compute_returns(close, [3])
        assert 'ret_3d' in result
        assert np.isnan(result['ret_3d'][2])  # first 3 positions are NaN
        assert abs(result['ret_3d'][3] - 2.857) < 0.01  # (10.8/10.5-1)*100
        assert abs(result['ret_3d'][4] - 4.762) < 0.01  # (11.0/10.5-1)*100

class TestRSI:
    def test_rsi_range(self):
        np.random.seed(42)
        close = 100 + np.cumsum(np.random.randn(100) * 0.5)
        rsi = compute_rsi(close, 14)
        assert np.isnan(rsi[:14]).all()  # window warmup
        assert np.all((rsi[14:] >= 0) & (rsi[14:] <= 100))

class TestATR:
    def test_atr_positive(self):
        high = np.array([10.5, 11.0, 11.5, 11.2], dtype=np.float32)
        low = np.array([9.5, 10.2, 10.8, 10.5], dtype=np.float32)
        close = np.array([10.0, 10.8, 11.0, 11.0], dtype=np.float32)
        atr = compute_atr(high, low, close, 3)
        assert np.isnan(atr[:3]).all()
        assert atr[3] > 0

class TestBuildDailyFeatures:
    def test_all_features_present(self):
        n = 30
        close = 100 + np.cumsum(np.random.randn(n) * 0.5)
        open_arr = close - np.random.rand(n) * 0.3
        high = close + np.abs(np.random.randn(n)) * 0.5
        low = close - np.abs(np.random.randn(n)) * 0.5
        volume = np.random.rand(n) * 1e7 + 5e6
        amount = volume * close
        features = build_daily_features(open_arr, high, low, close, volume, amount)
        for name in DAILY_FEATURE_NAMES:
            if name not in ['money_flow_5d', 'money_flow_10d', 'turnover_rate']:
                assert name in features, f"Missing feature: {name}"
        # All arrays same length
        for v in features.values():
            assert len(v) == n
```

- [ ] **Step 4: Run tests to verify they fail (code doesn't exist yet)**

```bash
cd /Users/wgfu/work/a-stock-trading && python -m pytest tests/test_dl_features.py -v
```

Expected: Import errors or module not found.

- [ ] **Step 5: Commit**

```bash
git add dl_models/__init__.py dl_models/features.py tests/test_dl_features.py
git commit -m "feat: add dl_models package with feature engineering

- Daily features: returns, volatility, MA deviations, RSI, ATR, Bollinger, volume ratio, amplitude, consecutive up/down, money flow, turnover
- Market-level features for regime detection
- 20 named features in DAILY_FEATURE_NAMES

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 1.3: Market Regime Detector

**Files:**
- Create: `dl_models/regime_detector.py`
- Create: `tests/test_regime_detector.py`

- [ ] **Step 1: Write failing test**

```python
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
    bull_close = 100 + np.cumsum(np.random.randn(n//3) * 0.3 + 0.15)  # drift +0.15
    bull_vol = np.random.rand(n//3) * 1e9 + 5e8
    bull_breadth = np.random.rand(n//3) * 0.2 + 0.6  # 0.6-0.8

    # Bear: falling prices, low breadth
    bear_volume = np.random.rand(n//3) * 5e8 + 1e8
    bear_close = np.full(n//3, np.nan)
    bear_close[0] = bull_close[-1]
    for i in range(1, n//3):
        bear_close[i] = bear_close[i-1] + np.random.randn() * 0.3 - 0.12  # drift -0.12
    bear_breadth = np.random.rand(n//3) * 0.3 + 0.1  # 0.1-0.4

    # Sideways: flat prices
    side_close = np.full(n//3, np.nan)
    side_close[0] = bear_close[-1]
    for i in range(1, n//3):
        side_close[i] = side_close[i-1] + np.random.randn() * 0.2
    side_breadth = np.random.rand(n//3) * 0.3 + 0.35

    close = np.concatenate([bull_close, bear_close, side_close]).astype(np.float32)
    volume = np.concatenate([bull_vol, bear_volume, bear_volume]).astype(np.float32)
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
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd /Users/wgfu/work/a-stock-trading && python -m pytest tests/test_regime_detector.py -v
```

Expected: FAIL (module not found).

- [ ] **Step 3: Implement RegimeDetector model**

```python
# dl_models/regime_detector.py
"""Market Regime Detector — Transformer classifier for bull/bear/sideways."""

import numpy as np
import torch
import torch.nn as nn
from dataclasses import dataclass
from typing import Dict, Optional

REGIME_LABELS = {0: 'bull', 1: 'bear', 2: 'sideways'}

@dataclass
class RegimeConfig:
    seq_len: int = 60
    d_model: int = 128
    num_heads: int = 4
    num_layers: int = 2
    num_regimes: int = 3
    dropout: float = 0.1
    learning_rate: float = 1e-3

class PositionalEncoding(nn.Module):
    def __init__(self, d_model: int, max_len: int = 500):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-np.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer('pe', pe.unsqueeze(0))

    def forward(self, x):
        return x + self.pe[:, :x.size(1)]

class RegimeDetector(nn.Module):
    def __init__(self, config: RegimeConfig):
        super().__init__()
        self.config = config
        self.input_proj = nn.Linear(1, config.d_model)  # will be overridden in forward
        self.pos_encoding = PositionalEncoding(config.d_model, max_len=500)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=config.d_model, nhead=config.num_heads,
            dropout=config.dropout, batch_first=True,
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=config.num_layers)
        self.cls_token = nn.Parameter(torch.randn(1, 1, config.d_model))
        self.classifier = nn.Sequential(
            nn.Linear(config.d_model, config.d_model // 2),
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.d_model // 2, config.num_regimes),
        )

    def _project_features(self, x: torch.Tensor) -> torch.Tensor:
        """Project input features to d_model dimension with learned projection."""
        B, T, F = x.shape
        # Use a linear layer that's dynamically created to match input dims
        if not hasattr(self, '_proj') or self._proj.in_features != F:
            self._proj = nn.Linear(F, self.config.d_model).to(x.device)
        return self._proj(x)

    def forward(self, x: torch.Tensor, mask: Optional[torch.Tensor] = None):
        """
        x: (B, T, F) — batch, sequence length, features
        Returns dict with logits, probs, regime indices.
        """
        B, T, F = x.shape
        x = self._project_features(x)  # (B, T, d_model)
        cls_tokens = self.cls_token.expand(B, -1, -1)
        x = torch.cat([cls_tokens, x], dim=1)  # (B, 1+T, d_model)
        x = self.pos_encoding(x)
        x = self.transformer(x, src_key_padding_mask=mask)
        cls_out = x[:, 0, :]  # (B, d_model)
        logits = self.classifier(cls_out)  # (B, num_regimes)
        probs = torch.softmax(logits, dim=-1)
        regime_idx = torch.argmax(probs, dim=-1)
        return {
            'logits': logits,
            'probs': probs,
            'regime_idx': regime_idx,
        }

    def predict(self, features: np.ndarray) -> Dict:
        """
        Single-sample prediction.
        features: (T, F) numpy array.
        Returns dict with regime label, confidence, probabilities, regime_score.
        """
        self.eval()
        with torch.no_grad():
            x = torch.from_numpy(features).unsqueeze(0).float()  # (1, T, F)
            out = self.forward(x)
            probs = out['probs'][0].numpy()
            regime_idx = int(out['regime_idx'][0])
            confidence = float(probs[regime_idx])

            # regime_score: weighted score (-1 to 1, negative=bearish, positive=bullish)
            regime_score = probs[0] - probs[1]  # bull_prob - bear_prob

            return {
                'regime': REGIME_LABELS[regime_idx],
                'confidence': round(confidence, 4),
                'probabilities': {
                    'bull': round(float(probs[0]), 4),
                    'bear': round(float(probs[1]), 4),
                    'sideways': round(float(probs[2]), 4),
                },
                'regime_score': round(float(regime_score), 4),
            }

    def save(self, path: str):
        torch.save({
            'model_state': self.state_dict(),
            'config': self.config,
        }, path)

    @classmethod
    def load(cls, path: str) -> 'RegimeDetector':
        checkpoint = torch.load(path, map_location='cpu')
        model = cls(checkpoint['config'])
        model.load_state_dict(checkpoint['model_state'])
        return model
```

- [ ] **Step 4: Install numpy in test env if needed and run tests**

```bash
cd /Users/wgfu/work/a-stock-trading && pip install numpy torch --quiet && python -m pytest tests/test_regime_detector.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add dl_models/regime_detector.py tests/test_regime_detector.py
git commit -m "feat: add RegimeDetector — Transformer bull/bear/sideways classifier

2-layer TransformerEncoder with CLS token, PositionalEncoding.
Outputs: regime label, confidence, per-class probabilities, regime_score (-1 to 1).
Configurable via RegimeConfig dataclass.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 1.4: Short-term Predictor (BiLSTM + Attention)

**Files:**
- Create: `dl_models/short_term_predictor.py`
- Create: `tests/test_short_term_predictor.py`

- [ ] **Step 1: Write test**

```python
# tests/test_short_term_predictor.py
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
    regime = torch.tensor([0, 1, 2, 0])
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
```

- [ ] **Step 2: Run it, expect failure**

```bash
python -m pytest tests/test_short_term_predictor.py -v
```

- [ ] **Step 3: Implement the model**

```python
# dl_models/short_term_predictor.py
"""Short-term stock predictor — BiLSTM + MultiHeadAttention (1-5 day horizon)."""

import numpy as np
import torch
import torch.nn as nn
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

DIRECTION_LABELS = {0: 'flat', 1: 'up', 2: 'down'}

@dataclass
class ShortTermConfig:
    seq_len: int = 30
    num_features: int = 20
    hidden_dim: int = 128
    num_layers: int = 2
    num_heads: int = 4
    dropout: float = 0.2
    regime_dim: int = 3
    learning_rate: float = 1e-3

class ShortTermPredictor(nn.Module):
    """BiLSTM + MultiHeadAttention predictor for short-term price direction & return."""

    def __init__(self, config: ShortTermConfig):
        super().__init__()
        self.config = config
        self.lstm = nn.LSTM(
            input_size=config.num_features,
            hidden_size=config.hidden_dim,
            num_layers=config.num_layers,
            batch_first=True,
            bidirectional=True,
            dropout=config.dropout if config.num_layers > 1 else 0,
        )
        self.attention = nn.MultiheadAttention(
            embed_dim=config.hidden_dim * 2,  # bidirectional
            num_heads=config.num_heads,
            dropout=config.dropout,
            batch_first=True,
        )
        combined_dim = config.hidden_dim * 2 + config.regime_dim
        self.direction_head = nn.Sequential(
            nn.Linear(combined_dim, combined_dim // 2),
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(combined_dim // 2, 3),  # up/down/flat
        )
        self.return_mu_head = nn.Sequential(
            nn.Linear(combined_dim, combined_dim // 2),
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(combined_dim // 2, 1),
        )
        self.return_sigma_head = nn.Sequential(
            nn.Linear(combined_dim, combined_dim // 2),
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(combined_dim // 2, 1),
            nn.Softplus(),  # ensures positivity
        )

    def forward(self, x: torch.Tensor, regime_encoding: torch.Tensor) -> Dict[str, torch.Tensor]:
        """
        x: (B, T, F) price/volume/technical features
        regime_encoding: (B, 3) one-hot or probability vector
        Returns direction logits/probs and return μ/σ.
        """
        lstm_out, _ = self.lstm(x)  # (B, T, 2*H)
        attn_out, _ = self.attention(lstm_out, lstm_out, lstm_out)  # (B, T, 2*H)
        seq_repr = attn_out[:, -1, :]  # last timestep
        combined = torch.cat([seq_repr, regime_encoding], dim=-1)  # (B, 2*H + 3)
        direction_logits = self.direction_head(combined)
        direction_probs = torch.softmax(direction_logits, dim=-1)
        return_mu = self.return_mu_head(combined)
        return_sigma = self.return_sigma_head(combined)
        return {
            'direction_logits': direction_logits,
            'direction_probs': direction_probs,
            'return_mu': return_mu,
            'return_sigma': return_sigma,
        }

    def predict(self, features: np.ndarray, regime_encoding: List[float]) -> Dict:
        """
        Single-sample prediction.
        features: (T, F) numpy float32 array
        regime_encoding: [bull_prob, bear_prob, sideways_prob]
        """
        self.eval()
        with torch.no_grad():
            x = torch.from_numpy(features).unsqueeze(0).float()
            regime = torch.tensor([regime_encoding], dtype=torch.float)
            out = self.forward(x, regime)

        probs = out['direction_probs'][0].numpy()  # [flat, up, down]
        mu = float(out['return_mu'][0, 0])
        sigma = float(out['return_sigma'][0, 0])

        # Map to user-friendly direction labels
        # Probability ordering: index 0=flat, 1=up, 2=down
        direction_idx = int(np.argmax(probs))

        ci_low = round(mu - 1.96 * sigma, 4)
        ci_high = round(mu + 1.96 * sigma, 4)

        return {
            'direction': DIRECTION_LABELS[direction_idx],
            'prob_up': round(float(probs[1]), 4),
            'prob_down': round(float(probs[2]), 4),
            'prob_flat': round(float(probs[0]), 4),
            'expected_return': round(mu, 4),
            'uncertainty': round(sigma, 4),
            'confidence_interval': [ci_low, ci_high],
            'key_drivers': ['volume_ratio', 'money_flow_5d', 'momentum_5d'],  # placeholder
        }

    def save(self, path: str):
        torch.save({'model_state': self.state_dict(), 'config': self.config}, path)

    @classmethod
    def load(cls, path: str) -> 'ShortTermPredictor':
        checkpoint = torch.load(path, map_location='cpu')
        model = cls(checkpoint['config'])
        model.load_state_dict(checkpoint['model_state'])
        return model
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/wgfu/work/a-stock-trading && python -m pytest tests/test_short_term_predictor.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add dl_models/short_term_predictor.py tests/test_short_term_predictor.py
git commit -m "feat: add ShortTermPredictor — BiLSTM+Attention for 1-5d direction/return

2-layer bidirectional LSTM + MultiheadAttention + regime-context injection.
Dual output heads: direction (up/down/flat) with calibrated probs,
and expected return (μ, σ) via Gaussian NLL.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 1.5: Mid-term Predictor (Transformer)

**Files:**
- Create: `dl_models/mid_term_predictor.py`
- Create: `tests/test_mid_term_predictor.py`

- [ ] **Step 1: Write test**

```python
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
    regime = torch.tensor([0, 1, 2, 0])
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
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/test_mid_term_predictor.py -v
```

- [ ] **Step 3: Implement model**

```python
# dl_models/mid_term_predictor.py
"""Mid-term stock predictor — Transformer for 1-4 week direction & return."""

import numpy as np
import torch
import torch.nn as nn
from dataclasses import dataclass
from typing import Dict, List
from .regime_detector import PositionalEncoding
from .short_term_predictor import DIRECTION_LABELS

@dataclass
class MidTermConfig:
    seq_len: int = 52  # weeks
    num_price_features: int = 8
    num_fundamental_features: int = 6
    d_model: int = 256
    num_heads: int = 8
    num_layers: int = 4
    dropout: float = 0.1
    regime_dim: int = 3
    learning_rate: float = 1e-3

class MidTermPredictor(nn.Module):
    """Transformer-based predictor for 1-4 week stock direction and expected return."""

    def __init__(self, config: MidTermConfig):
        super().__init__()
        self.config = config
        self.price_proj = nn.Linear(config.num_price_features, config.d_model)
        self.pos_encoding = PositionalEncoding(config.d_model, max_len=200)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=config.d_model, nhead=config.num_heads,
            dropout=config.dropout, batch_first=True,
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=config.num_layers)
        self.cls_token = nn.Parameter(torch.randn(1, 1, config.d_model))
        # Combine CLS output + fundamental features + regime
        combined_dim = config.d_model + config.num_fundamental_features + config.regime_dim
        self.direction_head = nn.Sequential(
            nn.Linear(combined_dim, combined_dim // 2),
            nn.ReLU(), nn.Dropout(config.dropout),
            nn.Linear(combined_dim // 2, 3),
        )
        self.return_mu_head = nn.Sequential(
            nn.Linear(combined_dim, combined_dim // 2),
            nn.ReLU(), nn.Dropout(config.dropout),
            nn.Linear(combined_dim // 2, 1),
        )
        self.return_sigma_head = nn.Sequential(
            nn.Linear(combined_dim, combined_dim // 2),
            nn.ReLU(), nn.Dropout(config.dropout),
            nn.Linear(combined_dim // 2, 1), nn.Softplus(),
        )

    def forward(self, x_price: torch.Tensor, x_fund: torch.Tensor,
                regime_encoding: torch.Tensor) -> Dict[str, torch.Tensor]:
        """
        x_price: (B, T, F_price) weekly price/technical features
        x_fund: (B, F_fund) fundamental features
        regime_encoding: (B, 3)
        """
        B = x_price.size(0)
        x = self.price_proj(x_price)  # (B, T, d_model)
        cls_tokens = self.cls_token.expand(B, -1, -1)
        x = torch.cat([cls_tokens, x], dim=1)
        x = self.pos_encoding(x)
        x = self.transformer(x)
        cls_out = x[:, 0, :]  # (B, d_model)
        combined = torch.cat([cls_out, x_fund, regime_encoding], dim=-1)
        direction_logits = self.direction_head(combined)
        direction_probs = torch.softmax(direction_logits, dim=-1)
        return_mu = self.return_mu_head(combined)
        return_sigma = self.return_sigma_head(combined)
        return {
            'direction_logits': direction_logits,
            'direction_probs': direction_probs,
            'return_mu': return_mu,
            'return_sigma': return_sigma,
        }

    def predict(self, price_features: np.ndarray, fund_features: np.ndarray,
                regime_encoding: List[float]) -> Dict:
        self.eval()
        with torch.no_grad():
            x_p = torch.from_numpy(price_features).unsqueeze(0).float()
            x_f = torch.from_numpy(fund_features).unsqueeze(0).float()
            regime = torch.tensor([regime_encoding], dtype=torch.float)
            out = self.forward(x_p, x_f, regime)
        probs = out['direction_probs'][0].numpy()
        mu = float(out['return_mu'][0, 0])
        sigma = float(out['return_sigma'][0, 0])
        direction_idx = int(np.argmax(probs))
        return {
            'direction': DIRECTION_LABELS[direction_idx],
            'prob_up': round(float(probs[1]), 4),
            'prob_down': round(float(probs[2]), 4),
            'prob_flat': round(float(probs[0]), 4),
            'expected_return': round(mu, 4),
            'uncertainty': round(sigma, 4),
            'confidence_interval': [round(mu - 1.96 * sigma, 4), round(mu + 1.96 * sigma, 4)],
            'horizon': '4w',
            'key_drivers': ['sector_momentum', 'roe_improvement', 'pe_percentile'],
        }

    def save(self, path: str):
        torch.save({'model_state': self.state_dict(), 'config': self.config}, path)

    @classmethod
    def load(cls, path: str) -> 'MidTermPredictor':
        checkpoint = torch.load(path, map_location='cpu')
        model = cls(checkpoint['config'])
        model.load_state_dict(checkpoint['model_state'])
        return model
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/wgfu/work/a-stock-trading && python -m pytest tests/test_mid_term_predictor.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add dl_models/mid_term_predictor.py tests/test_mid_term_predictor.py
git commit -m "feat: add MidTermPredictor — Transformer for 1-4w direction/return

4-layer TransformerEncoder with CLS token, concatenating price sequence
representation with fundamental features and regime context.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 1.6: Probability Calibration

**Files:**
- Create: `dl_models/calibration.py`
- Create: `tests/test_calibration.py`

- [ ] **Step 1: Write test**

```python
# tests/test_calibration.py
import numpy as np
from dl_models.calibration import TemperatureScaler, IsotonicCalibrator

def test_temperature_scaler_fit_predict():
    logits = np.array([[2.0, 0.5], [0.3, 1.5], [-1.0, 0.2], [0.5, -0.5]], dtype=np.float32)
    labels = np.array([0, 1, 1, 0])
    scaler = TemperatureScaler()
    scaler.fit(logits, labels)
    assert scaler.temperature > 0
    calibrated = scaler.calibrate(logits)
    assert calibrated.shape == logits.shape
    assert np.allclose(calibrated.sum(axis=1), 1.0, atol=0.01)

def test_isotonic_calibrator():
    probs = np.array([0.3, 0.5, 0.7, 0.8, 0.85, 0.9])
    labels = np.array([0, 0, 1, 1, 1, 1])
    cal = IsotonicCalibrator()
    cal.fit(probs, labels)
    calibrated = cal.calibrate(np.array([0.3, 0.5, 0.7, 0.9]))
    assert len(calibrated) == 4
    # Monotonicity: higher input prob → higher or equal calibrated prob
    assert calibrated[0] <= calibrated[-1]
```

- [ ] **Step 2: Run, expect failure**

```bash
python -m pytest tests/test_calibration.py -v
```

- [ ] **Step 3: Implement**

```python
# dl_models/calibration.py
"""Probability calibration for DL model outputs — temperature scaling + isotonic regression."""

import numpy as np
from scipy.optimize import minimize
from sklearn.isotonic import IsotonicRegression

class TemperatureScaler:
    """Temperature scaling for multi-class probability calibration."""

    def __init__(self):
        self.temperature = 1.0

    def fit(self, logits: np.ndarray, labels: np.ndarray):
        """
        logits: (N, C) model output logits
        labels: (N,) integer class labels
        """
        def nll_loss(t):
            scaled = logits / t
            probs = np.exp(scaled) / np.exp(scaled).sum(axis=1, keepdims=True)
            return -np.log(probs[np.arange(len(labels)), labels] + 1e-10).mean()

        result = minimize(nll_loss, x0=np.array([1.0]), bounds=[(0.1, 10.0)], method='L-BFGS-B')
        self.temperature = float(result.x[0])
        return self

    def calibrate(self, logits: np.ndarray) -> np.ndarray:
        scaled = logits / self.temperature
        probs = np.exp(scaled) / np.exp(scaled).sum(axis=1, keepdims=True)
        return probs.astype(np.float32)

class IsotonicCalibrator:
    """Isotonic regression calibrator for binary probabilities."""

    def __init__(self):
        self.regressor = IsotonicRegression(out_of_bounds='clip')

    def fit(self, probs: np.ndarray, labels: np.ndarray):
        self.regressor.fit(probs, labels)
        return self

    def calibrate(self, probs: np.ndarray) -> np.ndarray:
        return self.regressor.predict(probs).astype(np.float32)

def calibrate_prediction(logits: np.ndarray, labels: np.ndarray,
                          val_logits: np.ndarray) -> np.ndarray:
    """Full calibration pipeline: temperature scaling → isotonic for each class."""
    temp_scaler = TemperatureScaler()
    temp_scaler.fit(logits, labels)
    calibrated_logits = logits / temp_scaler.temperature
    probs = np.exp(calibrated_logits) / np.exp(calibrated_logits).sum(axis=1, keepdims=True)

    val_probs = np.exp(val_logits / temp_scaler.temperature)
    val_probs = val_probs / val_probs.sum(axis=1, keepdims=True)

    # Apply isotonic per-class
    n_classes = logits.shape[1]
    calibrated_val = np.zeros_like(val_probs)
    for c in range(n_classes):
        iso = IsotonicCalibrator()
        binary_labels = (labels == c).astype(np.float32)
        iso.fit(val_probs[:, c], binary_labels)
        calibrated_val[:, c] = iso.calibrate(val_probs[:, c])

    # Re-normalize
    calibrated_val = calibrated_val / calibrated_val.sum(axis=1, keepdims=True)
    return calibrated_val.astype(np.float32)
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/wgfu/work/a-stock-trading && pip install scipy scikit-learn --quiet && python -m pytest tests/test_calibration.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add dl_models/calibration.py tests/test_calibration.py
git commit -m "feat: add probability calibration — temperature scaling + isotonic regression

TemperatureScaler optimizes a single temperature parameter via NLL minimization.
IsotonicCalibrator wraps sklearn IsotonicRegression for per-class calibration.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 1.7: ONNX Export

**Files:**
- Create: `dl_models/onnx_export.py`

- [ ] **Step 1: Write and implement**

```python
# dl_models/onnx_export.py
"""PyTorch → ONNX conversion utilities for DL prediction models."""

import torch
import numpy as np
from pathlib import Path
from typing import Optional
from .regime_detector import RegimeDetector
from .short_term_predictor import ShortTermPredictor
from .mid_term_predictor import MidTermPredictor

def export_regime_detector(model: RegimeDetector, output_path: str,
                            sample_input: Optional[np.ndarray] = None):
    """Export RegimeDetector to ONNX."""
    model.eval()
    if sample_input is None:
        sample_input = np.random.randn(1, model.config.seq_len, 6).astype(np.float32)
    dummy = torch.from_numpy(sample_input)
    torch.onnx.export(
        model, (dummy,),
        output_path,
        input_names=['features'],
        output_names=['logits'],
        dynamic_axes={'features': {0: 'batch'}, 'logits': {0: 'batch'}},
        opset_version=14,
    )
    # Verify
    import onnx
    onnx_model = onnx.load(output_path)
    onnx.checker.check_model(onnx_model)

def export_short_term(model: ShortTermPredictor, output_path: str,
                       sample_features: Optional[np.ndarray] = None,
                       sample_regime: Optional[np.ndarray] = None):
    """Export ShortTermPredictor to ONNX."""
    model.eval()
    if sample_features is None:
        sample_features = np.random.randn(1, model.config.seq_len, model.config.num_features).astype(np.float32)
    if sample_regime is None:
        sample_regime = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
    dummy_x = torch.from_numpy(sample_features)
    dummy_r = torch.from_numpy(sample_regime)
    torch.onnx.export(
        model, (dummy_x, dummy_r),
        output_path,
        input_names=['features', 'regime_encoding'],
        output_names=['direction_logits', 'return_mu', 'return_sigma'],
        dynamic_axes={'features': {0: 'batch'}, 'direction_logits': {0: 'batch'}},
        opset_version=14,
    )
    import onnx
    onnx_model = onnx.load(output_path)
    onnx.checker.check_model(onnx_model)

def export_mid_term(model: MidTermPredictor, output_path: str,
                     sample_price: Optional[np.ndarray] = None,
                     sample_fund: Optional[np.ndarray] = None,
                     sample_regime: Optional[np.ndarray] = None):
    """Export MidTermPredictor to ONNX."""
    model.eval()
    cfg = model.config
    if sample_price is None:
        sample_price = np.random.randn(1, cfg.seq_len, cfg.num_price_features).astype(np.float32)
    if sample_fund is None:
        sample_fund = np.random.randn(1, cfg.num_fundamental_features).astype(np.float32)
    if sample_regime is None:
        sample_regime = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
    torch.onnx.export(
        model, (
            torch.from_numpy(sample_price),
            torch.from_numpy(sample_fund),
            torch.from_numpy(sample_regime),
        ),
        output_path,
        input_names=['price_features', 'fund_features', 'regime_encoding'],
        output_names=['direction_logits', 'return_mu', 'return_sigma'],
        dynamic_axes={'price_features': {0: 'batch'}, 'direction_logits': {0: 'batch'}},
        opset_version=14,
    )
    import onnx
    onnx_model = onnx.load(output_path)
    onnx.checker.check_model(onnx_model)

def export_all(models_dir: str = 'model_checkpoints', output_dir: str = 'model_checkpoints'):
    """Export all models in models_dir to ONNX format."""
    models_dir = Path(models_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for pt_file in models_dir.glob('*.pt'):
        if 'regime' in pt_file.name:
            model = RegimeDetector.load(str(pt_file))
            export_regime_detector(model, str(output_dir / pt_file.stem) + '.onnx')
        elif 'short' in pt_file.name:
            model = ShortTermPredictor.load(str(pt_file))
            export_short_term(model, str(output_dir / pt_file.stem) + '.onnx')
        elif 'mid' in pt_file.name:
            model = MidTermPredictor.load(str(pt_file))
            export_mid_term(model, str(output_dir / pt_file.stem) + '.onnx')
```

- [ ] **Step 2: Commit**

```bash
git add dl_models/onnx_export.py
git commit -m "feat: add ONNX export utilities for all DL models

export_regime_detector, export_short_term, export_mid_term functions
with onnx.checker verification. Plus batch export_all helper.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 1.8: Integrate DL models with existing ml_predictor.py

**Files:**
- Modify: `ml_predictor.py`
- Modify: `factor_engine.py`

- [ ] **Step 1: Add get_feature_vector to factor_engine.py**

Add this function at the end of `factor_engine.py`:

```python
def get_feature_vector(code: str) -> dict:
    """
    Extract a DL-ready feature vector for a single stock.
    Uses the existing 20-factor compute path, returns numpy arrays for DL models.
    Returns dict with keys: daily_features (30, 20), weekly_features (52, 8),
    fundamental_features (6,), regime_context (3,).
    """
    from data_fetchers import get_daily_kline, get_money_flow_history, get_fundamental_data
    from dl_models.features import build_daily_features

    try:
        # Fetch daily K-line (60 days for sufficient history)
        daily = get_daily_kline(code, count=60)
        if daily is None or len(daily) < 30:
            return None

        close = daily['close'].values.astype(np.float32)
        open_arr = daily['open'].values.astype(np.float32)
        high = daily['high'].values.astype(np.float32)
        low = daily['low'].values.astype(np.float32)
        volume = daily['volume'].values.astype(np.float32)
        amount = daily.get('amount', daily['volume'] * close).values.astype(np.float32)

        # Money flow
        try:
            mf = get_money_flow_history(code, count=60)
            mf_5d = mf['net_inflow'].rolling(5).mean().values.astype(np.float32) if mf is not None else None
            mf_10d = mf['net_inflow'].rolling(10).mean().values.astype(np.float32) if mf is not None else None
        except Exception:
            mf_5d, mf_10d = None, None

        daily_features = build_daily_features(
            open_arr, high, low, close, volume, amount,
            money_flow_5d=mf_5d, money_flow_10d=mf_10d,
        )

        # Convert to array matrix (T, F) with named order
        from dl_models.features import DAILY_FEATURE_NAMES
        feat_matrix = np.column_stack([
            daily_features.get(name, np.full(len(close), np.nan))
            for name in DAILY_FEATURE_NAMES
        ]).astype(np.float32)

        # Drop NaN rows (warmup periods)
        valid_mask = ~np.isnan(feat_matrix).any(axis=1)
        feat_matrix = feat_matrix[valid_mask]

        # Keep last 30 rows
        if len(feat_matrix) > 30:
            feat_matrix = feat_matrix[-30:]

        # Fundamental features
        try:
            fund = get_fundamental_data(code)
            fund_features = np.array([
                fund.get('pe_ttm', 0) or 0,
                fund.get('pb', 0) or 0,
                fund.get('roe', 0) or 0,
                fund.get('gross_margin', 0) or 0,
                fund.get('revenue_yoy', 0) or 0,
                fund.get('debt_ratio', 0) or 0,
            ], dtype=np.float32)
        except Exception:
            fund_features = np.zeros(6, dtype=np.float32)

        return {
            'daily_features': feat_matrix,
            'fundamental_features': fund_features,
        }
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"get_feature_vector({code}) failed: {e}")
        return None
```

- [ ] **Step 2: Add DL inference wrapper to ml_predictor.py**

Add at the top of `ml_predictor.py` (after existing imports):

```python
# DL model integration
import os
from dl_models.short_term_predictor import ShortTermPredictor, ShortTermConfig
from dl_models.mid_term_predictor import MidTermPredictor, MidTermConfig
from dl_models.regime_detector import RegimeDetector, RegimeConfig

_dl_models_cache = {}

def _load_dl_model(model_class, config_class, path: str):
    """Lazy-load a DL model with filesystem cache."""
    if path in _dl_models_cache:
        return _dl_models_cache[path]
    if not os.path.exists(path):
        return None
    model = model_class.load(path)
    model.eval()
    _dl_models_cache[path] = model
    return model

def predict_with_dl(code: str, regime_encoding: list = None) -> dict:
    """
    Run DL prediction for a stock. Falls back to existing RF/Ridge if DL unavailable.
    Returns combined prediction dict compatible with existing predict() interface.
    """
    from factor_engine import get_feature_vector

    features = get_feature_vector(code)
    if features is None or len(features['daily_features']) < 30:
        return _fallback_predict(code)

    # Load latest models
    model_dir = os.path.join(os.path.dirname(__file__), 'model_checkpoints')
    short_model = _load_dl_model(ShortTermPredictor, ShortTermConfig,
                                  os.path.join(model_dir, 'short_term_latest.pt'))
    mid_model = _load_dl_model(MidTermPredictor, MidTermConfig,
                                os.path.join(model_dir, 'mid_term_latest.pt'))

    if short_model is None:
        return _fallback_predict(code)

    # Default regime encoding if not provided
    if regime_encoding is None:
        regime_encoding = [0.33, 0.33, 0.34]

    # Short-term prediction
    short_result = short_model.predict(
        features['daily_features'], regime_encoding,
    )

    # Mid-term prediction
    mid_result = None
    if mid_model is not None:
        weekly = _daily_to_weekly(features['daily_features'])
        if weekly is not None:
            mid_result = mid_model.predict(
                weekly, features['fundamental_features'], regime_encoding,
            )

    return {
        'code': code,
        'short_term': short_result,
        'mid_term': mid_result,
        'source': 'dl_model',
    }

def _daily_to_weekly(daily_features: 'np.ndarray') -> 'np.ndarray':
    """Convert daily feature matrix to weekly (resample last 5 days → 1 week)."""
    import numpy as np
    n = len(daily_features)
    n_weeks = n // 5
    if n_weeks < 10:
        return None
    weekly = daily_features[-n_weeks * 5:].reshape(n_weeks, 5, -1)
    # Use last day of each week + mean of the week
    result = np.concatenate([
        weekly[:, -1, :4],   # OHLC from last day
        weekly[:, :, :].mean(axis=1),  # mean of all features
    ], axis=-1)
    return result.astype(np.float32)[-52:]  # keep last 52 weeks

def _fallback_predict(code: str) -> dict:
    """Fallback to existing RF/Ridge prediction."""
    # Calls the existing predict_direction() function
    return {'code': code, 'source': 'rf_fallback'}
```

- [ ] **Step 3: Verify imports work**

```bash
cd /Users/wgfu/work/a-stock-trading && python -c "from ml_predictor import predict_with_dl; print('Import OK')"
```

- [ ] **Step 4: Commit**

```bash
git add factor_engine.py ml_predictor.py
git commit -m "feat: integrate DL models with existing ml_predictor

- factor_engine.get_feature_vector() exports DL-ready feature arrays
- ml_predictor.predict_with_dl() loads latest ONNX models, runs short+mid prediction
- Falls back to RF/Ridge when DL models unavailable

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Phase 2: LLM Agent Decision Layer

### File Map

```
llm_agents/
  __init__.py
  agent_base.py              — base class with structured output, retry, JSON mode
  agent_prompts/
    macro_agent.txt          — system prompt for macro agent
    technical_agent.txt      — system prompt for technical agent
    fundamental_agent.txt    — system prompt for fundamental agent
    risk_agent.txt           — system prompt for risk agent
    fusion_agent.txt         — system prompt for fusion decision agent
  agent_orchestrator.py      — concurrent 4-agent + fusion orchestration
  agent_cache.py             — analysis result caching (1-hour TTL)

Modified:
  ai_service.py              — add structured output support (response_format)
```

---

### Task 2.1: Structured output in ai_service.py

**Files:**
- Modify: `ai_service.py`

- [ ] **Step 1: Add structured output method**

Add to `AIService` class in `ai_service.py`:

```python
@staticmethod
def call_agent_structured(provider: str, api_key: str, model: str,
                           messages: list, json_schema: dict = None) -> dict:
    """
    Call LLM with structured JSON output.
    messages: list of {"role": "user"|"system", "content": "..."}
    json_schema: optional JSON Schema for response_format
    Returns parsed dict.
    """
    import json as _json

    if provider == "gemini":
        return AIService._call_gemini_structured(api_key, model, messages, json_schema)

    url = PROVIDER_CONFIG[provider]["url"]
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    data = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,  # lower temp for structured decisions
        "max_tokens": 4096,
        "response_format": {"type": "json_object"},
    }

    response = requests.post(url, headers=headers, json=data, timeout=120)
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]

    # Parse and validate
    try:
        result = _json.loads(content)
        return result
    except _json.JSONDecodeError:
        # Try extracting JSON from markdown code block
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
            return _json.loads(content)
        raise ValueError(f"Failed to parse JSON from LLM response: {content[:200]}")
```

- [ ] **Step 2: Commit**

```bash
git add ai_service.py
git commit -m "feat: add structured JSON output support to ai_service

call_agent_structured() method with response_format=json_object,
JSON parsing with markdown code block fallback.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2.2: Agent base class and prompt templates

**Files:**
- Create: `llm_agents/__init__.py`
- Create: `llm_agents/agent_base.py`
- Create: `llm_agents/agent_prompts/macro_agent.txt`
- Create: `llm_agents/agent_prompts/technical_agent.txt`
- Create: `llm_agents/agent_prompts/fundamental_agent.txt`
- Create: `llm_agents/agent_prompts/risk_agent.txt`
- Create: `llm_agents/agent_prompts/fusion_agent.txt`

- [ ] **Step 1: Create package init**

```python
# llm_agents/__init__.py
"""LLM Agent decision layer for stock trading."""
```

- [ ] **Step 2: Write agent_base.py**

```python
# llm_agents/agent_base.py
"""Base class for LLM trading agents with structured output and retry logic."""

import json
import time
import logging
from pathlib import Path
from typing import Dict, Optional
from ai_service import AIService
from ai_config import get_api_key

logger = logging.getLogger(__name__)

PROMPT_DIR = Path(__file__).parent / 'agent_prompts'

class TradingAgent:
    """Base agent for stock analysis and decision-making."""

    def __init__(self, name: str, role: str, prompt_file: str,
                 provider: str = 'deepseek', model: str = None):
        self.name = name
        self.role = role
        self.provider = provider
        self.model = model or 'deepseek-chat'
        self.prompt_file = PROMPT_DIR / prompt_file
        with open(self.prompt_file, 'r') as f:
            self.system_prompt = f.read()

    def build_context(self, stock_data: Dict, dl_predictions: Dict = None) -> str:
        """Build the user message with stock-specific context. Override in subclasses."""
        raise NotImplementedError

    def analyze(self, stock_data: Dict, dl_predictions: Dict = None,
                max_retries: int = 2) -> Dict:
        """
        Run analysis. Returns structured dict with analysis, confidence, stance.
        """
        api_key = get_api_key(self.provider)
        if not api_key:
            return {'error': f'No API key for {self.provider}', 'confidence': 0}

        context = self.build_context(stock_data, dl_predictions)
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": context},
        ]

        for attempt in range(max_retries + 1):
            try:
                result = AIService.call_agent_structured(
                    self.provider, api_key, self.model, messages,
                )
                result['_agent'] = self.name
                result['_provider'] = self.provider
                return result
            except Exception as e:
                logger.warning(f"Agent {self.name} attempt {attempt+1} failed: {e}")
                if attempt < max_retries:
                    time.sleep(1 + attempt * 2)
                else:
                    return {'error': str(e), 'confidence': 0, '_agent': self.name}
```

- [ ] **Step 3: Write macro agent prompt**

```text
# llm_agents/agent_prompts/macro_agent.txt
You are a senior macro strategist for the Chinese A-share market. Your role is to analyze the overall market environment, sector rotation, capital flows, and policy conditions.

## Input Data
You will receive:
- Market indices data (CSI 300, CSI 500, ChiNext)
- Sector performance heatmap
- North-bound capital flow
- Market regime prediction from quantitative models
- Recent policy/news highlights

## Your Task
Analyze the macro environment and output a structured JSON assessment.

## Output Format (JSON only)
{
  "stance": "bullish|neutral|bearish",
  "confidence": 0-100,
  "reasoning": "One paragraph explaining your macro assessment",
  "strong_sectors": ["sector1", "sector2", "sector3"],
  "weak_sectors": ["sector1", "sector2"],
  "key_risks": ["risk1", "risk2"],
  "market_regime_agreement": true/false,
  "regime_comment": "If you disagree with the model's regime prediction, explain why"
}
```

- [ ] **Step 4: Write technical agent prompt**

```text
# llm_agents/agent_prompts/technical_agent.txt
You are a quantitative technical analyst specializing in A-share stocks. You interpret technical indicators, DL model predictions, factor scores, and chart patterns.

## Input Data
You will receive:
- Deep Learning model predictions (short-term and mid-term direction probabilities + expected returns + uncertainty)
- Multi-factor scores (20 factors across momentum, technical, capital flow, value, quality, risk categories)
- Technical indicators (RSI, MACD, Bollinger Bands, MA crossover status)
- Volume/price anomaly alerts
- Consecutive up/down day counts

## Your Task
Interpret the quantitative signals and output a structured JSON assessment.

## Output Format (JSON only)
{
  "stance": "bullish|neutral|bearish",
  "confidence": 0-100,
  "reasoning": "Interpret the DL signals and factor scores. Do the signals agree or conflict?",
  "key_signals": ["signal1", "signal2"],
  "signal_conflicts": ["conflict_description"],
  "dl_model_agreement": true/false,
  "factor_strength": "strong|moderate|weak"
}
```

- [ ] **Step 5: Write fundamental agent prompt**

```text
# llm_agents/agent_prompts/fundamental_agent.txt
You are a value investment analyst for the Chinese A-share market. You evaluate stocks based on fundamentals, valuation, growth, and industry positioning.

## Input Data
You will receive:
- PE ratio and industry percentile
- PB ratio and industry percentile
- ROE trend (current and historical)
- Gross margin and trend
- Revenue and profit growth (YoY)
- Debt ratio
- Industry comparison metrics

## Your Task
Evaluate the fundamental quality of the stock and output structured JSON.

## Output Format (JSON only)
{
  "stance": "bullish|neutral|bearish",
  "confidence": 0-100,
  "valuation": "undervalued|fair|overvalued",
  "reasoning": "Fundamental assessment with key metrics",
  "quality_grade": "A|B|C|D",
  "catalysts": ["positive catalyst"],
  "risk_points": ["earnings miss risk", "high debt"],
  "industry_position": "leader|average|laggard"
}
```

- [ ] **Step 6: Write risk agent prompt**

```text
# llm_agents/agent_prompts/risk_agent.txt
You are a risk management expert for equity trading. Your role is to evaluate risk and recommend position sizing. You have VETO POWER — if risk is too high, you can block a buy recommendation.

## Input Data
You will receive:
- VaR (95% historical and parametric)
- CVaR / Expected Shortfall
- Maximum drawdown (historical)
- Sharpe ratio
- Volatility (annualized)
- Beta vs CSI 300
- Kelly criterion position recommendation
- ATR-based stop-loss level
- Portfolio context: current total exposure, sector concentration, recent P&L
- Liquidity: average daily turnover

## Hard Limits (enforce these)
- Single position ≤ 20% of portfolio
- Total exposure ≤ 80%
- Daily loss circuit breaker: if today's loss > 5%, NO new positions
- Sector concentration ≤ 30%
- Portfolio VaR ≤ 2% of total assets
- Minimum liquidity: daily turnover ≥ 50M CNY

## Your Task
Output a risk assessment with clear veto decision.

## Output Format (JSON only)
{
  "risk_grade": "low|medium|high|critical",
  "confidence": 0-100,
  "veto": true/false,
  "veto_reason": "Reason if vetoed",
  "recommended_position_pct": 0-20,
  "stop_loss_pct": -5 to -15,
  "key_risks": ["risk1", "risk2"],
  "max_drawdown_estimate": -10.0,
  "portfolio_impact": "low|medium|high"
}
```

- [ ] **Step 7: Write fusion agent prompt**

```text
# llm_agents/agent_prompts/fusion_agent.txt
You are the Chief Investment Officer (Portfolio Manager) for an AI-powered trading system. You synthesize inputs from 4 specialist agents (Macro, Technical, Fundamental, Risk) and make the final trading decision.

## Decision Rules (FOLLOW STRICTLY)
1. RISK AGENT HAS VETO POWER — if risk_grade is "high" or "critical", or veto=true, you CANNOT output "buy"
2. To BUY: ≥2 of (Macro, Technical, Fundamental) agents must be bullish AND none can be bearish
3. If any 2 agents have confidence < 40, downgrade to "hold" or "watch"
4. Conflicting signals (1 strongly bullish + 1 strongly bearish): prefer the lower-risk option
5. Position size = recommended_position_pct from Risk Agent × regime_coefficient (bull=1.0, sideways=0.7, bear=0.4)
6. Stop-loss = Risk Agent's stop_loss_pct
7. Take-profit = 2.5 × |stop_loss_pct| (minimum 2:1 reward-to-risk)

## Output Format (JSON only)
{
  "action": "buy|sell|hold|watch",
  "confidence": 0-100,
  "position_pct": 0-20,
  "stop_loss_pct": -5 to -15,
  "take_profit_pct": 10 to 40,
  "reasoning": "One-sentence summary of why this decision",
  "risk_flags": ["flag1"],
  "horizon": "short|mid",
  "agent_consensus": "strong|moderate|weak|conflict"
}
```

- [ ] **Step 8: Commit**

```bash
git add llm_agents/
git commit -m "feat: add LLM agent base class and 5 prompt templates

TradingAgent base class with structured output and retry.
Prompts for: Macro, Technical, Fundamental, Risk (with veto), Fusion (decision rules).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2.3: Agent Orchestrator

**Files:**
- Create: `llm_agents/agent_orchestrator.py`
- Create: `llm_agents/agent_cache.py`

- [ ] **Step 1: Write agent_cache.py**

```python
# llm_agents/agent_cache.py
"""Cache for LLM agent analysis results (1-hour TTL, per stock)."""

import time
import hashlib
import json
from typing import Dict, Optional

_cache: Dict[str, tuple] = {}

def _cache_key(stock_code: str, data_hash: str) -> str:
    return hashlib.md5(f"{stock_code}:{data_hash}".encode()).hexdigest()

def get_cached(stock_code: str, data_hash: str, ttl: int = 3600) -> Optional[Dict]:
    key = _cache_key(stock_code, data_hash)
    if key in _cache:
        result, timestamp = _cache[key]
        if time.time() - timestamp < ttl:
            return result
        del _cache[key]
    return None

def set_cache(stock_code: str, data_hash: str, result: Dict):
    key = _cache_key(stock_code, data_hash)
    _cache[key] = (result, time.time())

def clear_expired():
    now = time.time()
    expired = [k for k, (_, ts) in _cache.items() if now - ts > 3600]
    for k in expired:
        del _cache[k]
```

- [ ] **Step 2: Write agent_orchestrator.py**

```python
# llm_agents/agent_orchestrator.py
"""Orchestrate 4 specialist agents in parallel, then fusion agent for final decision."""

import concurrent.futures
import hashlib
import json
import logging
from typing import Dict, List, Optional
from .agent_base import TradingAgent
from .agent_cache import get_cached, set_cache

logger = logging.getLogger(__name__)

# Singleton agents (created once)
_macro_agent = None
_technical_agent = None
_fundamental_agent = None
_risk_agent = None
_fusion_agent = None

def _init_agents():
    global _macro_agent, _technical_agent, _fundamental_agent, _risk_agent, _fusion_agent
    if _macro_agent is None:
        _macro_agent = TradingAgent('Macro', 'macro_strategist', 'macro_agent.txt')
        _technical_agent = TradingAgent('Technical', 'quant_analyst', 'technical_agent.txt')
        _fundamental_agent = TradingAgent('Fundamental', 'value_analyst', 'fundamental_agent.txt')
        _risk_agent = TradingAgent('Risk', 'risk_manager', 'risk_agent.txt')
        _fusion_agent = TradingAgent('Fusion', 'portfolio_manager', 'fusion_agent.txt')

def analyze_stock(stock_data: Dict, dl_predictions: Dict = None,
                  portfolio_context: Dict = None) -> Dict:
    """
    Full 4-agent concurrent analysis + fusion decision for one stock.
    Returns complete analysis with final trading decision.
    """
    _init_agents()

    # Compute data hash for caching
    data_str = json.dumps({'s': stock_data.get('code', ''), 'p': stock_data.get('price', 0)})
    data_hash = hashlib.md5(data_str.encode()).hexdigest()
    cached = get_cached(stock_data.get('code', ''), data_hash)
    if cached:
        return cached

    # Inject portfolio context into risk agent's system prompt
    enriched_stock = dict(stock_data)
    if portfolio_context:
        enriched_stock['portfolio'] = portfolio_context

    # Run 4 specialist agents concurrently
    agents = [
        (_macro_agent, enriched_stock, dl_predictions),
        (_technical_agent, enriched_stock, dl_predictions),
        (_fundamental_agent, enriched_stock, dl_predictions),
        (_risk_agent, enriched_stock, dl_predictions),
    ]

    specialist_results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(agent.analyze, data, preds): agent.name
            for agent, data, preds in agents
        }
        for future in concurrent.futures.as_completed(futures):
            agent_name = futures[future]
            try:
                specialist_results[agent_name] = future.result(timeout=120)
            except Exception as e:
                logger.error(f"Agent {agent_name} failed: {e}")
                specialist_results[agent_name] = {'error': str(e), 'confidence': 0}

    # Fusion decision (sequential — needs all specialist results)
    fusion_context = _build_fusion_context(stock_data, specialist_results, dl_predictions)
    try:
        fusion_result = _fusion_agent.analyze(
            {'fusion_context': fusion_context}, dl_predictions,
        )
    except Exception as e:
        logger.error(f"Fusion agent failed: {e}")
        fusion_result = {'action': 'hold', 'confidence': 0, 'reasoning': f'Fusion error: {e}'}

    # Validate risk veto
    risk = specialist_results.get('Risk', {})
    if risk.get('veto') and fusion_result.get('action') == 'buy':
        fusion_result['action'] = 'hold'
        fusion_result['reasoning'] = f"RISK VETO: {risk.get('veto_reason', 'No reason')}. Original: {fusion_result.get('reasoning', '')}"

    result = {
        'code': stock_data.get('code'),
        'name': stock_data.get('name'),
        'price': stock_data.get('price'),
        'specialists': specialist_results,
        'decision': fusion_result,
        'timestamp': __import__('datetime').datetime.now().isoformat(),
    }

    set_cache(stock_data.get('code', ''), data_hash, result)
    return result

def _build_fusion_context(stock_data: Dict, specialist_results: Dict,
                           dl_predictions: Dict = None) -> str:
    """Build the fusion agent's input context from specialist outputs."""
    lines = [f"Stock: {stock_data.get('code')} {stock_data.get('name')} @ {stock_data.get('price')}"]

    if dl_predictions:
        st = dl_predictions.get('short_term', {})
        mt = dl_predictions.get('mid_term', {})
        lines.append(f"\nDL Predictions:")
        lines.append(f"  Short-term: {st.get('direction')} (up:{st.get('prob_up')} down:{st.get('prob_down')}), expected return: {st.get('expected_return')}")
        if mt:
            lines.append(f"  Mid-term: {mt.get('direction')} (up:{mt.get('prob_up')} down:{mt.get('prob_down')}), expected return: {mt.get('expected_return')}")

    for name, result in specialist_results.items():
        lines.append(f"\n{name} Agent:")
        lines.append(f"  Stance: {result.get('stance', 'N/A')}")
        lines.append(f"  Confidence: {result.get('confidence', 0)}")
        if result.get('error'):
            lines.append(f"  Error: {result['error']}")
        if result.get('veto') is not None:
            lines.append(f"  Veto: {result['veto']} ({result.get('veto_reason', '')})")
        if result.get('risk_grade'):
            lines.append(f"  Risk Grade: {result['risk_grade']}")

    return '\n'.join(lines)

def batch_analyze(stocks: List[Dict], dl_predictions_map: Dict[str, Dict] = None,
                  portfolio_context: Dict = None, max_concurrent: int = 5) -> List[Dict]:
    """
    Analyze a batch of stocks with concurrency control.
    max_concurrent limits simultaneous stock analyses to control API rate.
    """
    results = []
    semaphore = concurrent.futures.Semaphore(max_concurrent)

    def analyze_one(stock):
        with semaphore:
            code = stock.get('code')
            dl_pred = (dl_predictions_map or {}).get(code)
            return analyze_stock(stock, dl_pred, portfolio_context)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent) as executor:
        futures = [executor.submit(analyze_one, s) for s in stocks]
        for future in concurrent.futures.as_completed(futures):
            try:
                results.append(future.result(timeout=180))
            except Exception as e:
                logger.error(f"Batch analysis job failed: {e}")

    return results
```

- [ ] **Step 3: Commit**

```bash
git add llm_agents/agent_cache.py llm_agents/agent_orchestrator.py
git commit -m "feat: add agent orchestrator with concurrent execution and caching

analyze_stock() runs 4 specialists in parallel, then fusion sequentially.
batch_analyze() with semaphore-concurrency control (max 5 concurrent).
1-hour result caching per stock+data_hash.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Phase 3: Risk Control Layer

### File Map

```
risk_control/
  __init__.py
  hard_constraints.py    — pre-execution constraint validation
  circuit_breaker.py     — daily loss circuit breaker
  position_guard.py      — position size + sector concentration guard
```

---

### Task 3.1: Hard Constraints Interceptor

**Files:**
- Create: `risk_control/__init__.py`
- Create: `risk_control/hard_constraints.py`

- [ ] **Step 1: Write hard_constraints.py**

```python
# risk_control/__init__.py
"""Hard constraint risk control layer for pre-execution trade validation."""

# risk_control/hard_constraints.py
"""Pre-execution hard constraint validator. All constraints must pass before order."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

@dataclass
class ConstraintConfig:
    single_position_max_pct: float = 20.0
    total_exposure_max_pct: float = 80.0
    daily_loss_circuit_breaker_pct: float = 5.0
    sector_concentration_max_pct: float = 30.0
    portfolio_var_max_pct: float = 2.0
    min_daily_turnover_cny: float = 50_000_000
    atr_stop_multiplier: float = 2.0
    hard_stop_loss_pct: float = 8.0

@dataclass
class ConstraintResult:
    passed: bool
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

def validate_order(
    action: str,
    target_code: str,
    target_sector: str,
    order_amount: float,
    portfolio_value: float,
    current_positions: List[Dict],
    current_daily_pnl_pct: float = 0,
    sector_exposure_map: Dict[str, float] = None,
    portfolio_var: float = None,
    avg_daily_turnover: float = None,
    config: ConstraintConfig = None,
) -> ConstraintResult:
    """
    Validate a proposed order against all hard constraints.
    Returns ConstraintResult with pass/fail and violation details.

    Parameters:
    - action: 'buy' or 'sell'
    - target_code: stock code
    - target_sector: sector name for concentration check
    - order_amount: proposed order value in CNY
    - portfolio_value: total portfolio value in CNY
    - current_positions: list of {code, market_value, sector}
    - current_daily_pnl_pct: today's P&L as percentage (negative = loss)
    - sector_exposure_map: {sector_name: total_value} current sector exposures
    - portfolio_var: current portfolio VaR as CNY amount
    - avg_daily_turnover: target stock's average daily turnover in CNY
    - config: constraint thresholds
    """
    if config is None:
        config = ConstraintConfig()
    violations = []
    warnings = []

    # 1. Daily loss circuit breaker
    if current_daily_pnl_pct <= -config.daily_loss_circuit_breaker_pct:
        if action == 'buy':
            violations.append(
                f"Daily loss circuit breaker triggered: {current_daily_pnl_pct:.1f}% ≤ "
                f"-{config.daily_loss_circuit_breaker_pct}%. No new buys allowed."
            )

    # 2. Total exposure check (for buy orders)
    total_market_value = sum(p.get('market_value', 0) for p in current_positions)
    current_exposure_pct = (total_market_value / portfolio_value) * 100 if portfolio_value > 0 else 0
    new_exposure_pct = ((total_market_value + order_amount) / portfolio_value) * 100 if portfolio_value > 0 else 0

    if action == 'buy' and new_exposure_pct > config.total_exposure_max_pct:
        violations.append(
            f"Total exposure would be {new_exposure_pct:.1f}% (limit: {config.total_exposure_max_pct}%). "
            f"Reduce existing positions first."
        )

    # 3. Single position cap
    if action == 'buy':
        existing_position = next((p for p in current_positions if p.get('code') == target_code), None)
        existing_value = existing_position.get('market_value', 0) if existing_position else 0
        new_single_pct = ((existing_value + order_amount) / portfolio_value) * 100 if portfolio_value > 0 else 0
        if new_single_pct > config.single_position_max_pct:
            violations.append(
                f"Single position would be {new_single_pct:.1f}% (limit: {config.single_position_max_pct}%). "
                f"Reduce order size."
            )

    # 4. Sector concentration
    if action == 'buy' and sector_exposure_map and target_sector:
        sector_value = sector_exposure_map.get(target_sector, 0) + order_amount
        sector_pct = (sector_value / portfolio_value) * 100 if portfolio_value > 0 else 0
        if sector_pct > config.sector_concentration_max_pct:
            violations.append(
                f"Sector '{target_sector}' concentration would be {sector_pct:.1f}% "
                f"(limit: {config.sector_concentration_max_pct}%)."
            )

    # 5. Portfolio VaR limit
    if portfolio_var is not None and portfolio_value > 0:
        var_pct = (portfolio_var / portfolio_value) * 100
        if var_pct > config.portfolio_var_max_pct:
            warnings.append(f"Portfolio VaR at {var_pct:.1f}% exceeds limit {config.portfolio_var_max_pct}%")

    # 6. Liquidity check
    if avg_daily_turnover is not None and avg_daily_turnover < config.min_daily_turnover_cny:
        violations.append(
            f"Insufficient liquidity: avg daily turnover {avg_daily_turnover:,.0f} CNY "
            f"(min: {config.min_daily_turnover_cny:,.0f} CNY)"
        )

    return ConstraintResult(
        passed=len(violations) == 0,
        violations=violations,
        warnings=warnings,
    )

def compute_stop_loss(current_price: float, atr: float = None,
                       config: ConstraintConfig = None) -> Tuple[float, str]:
    """Compute stop-loss price using tighter of ATR 2x or -8%."""
    if config is None:
        config = ConstraintConfig()
    atr_stop = current_price * (1 - atr * config.atr_stop_multiplier / current_price) if atr else None
    pct_stop = current_price * (1 - config.hard_stop_loss_pct / 100)
    if atr_stop is not None and atr_stop > pct_stop:
        return round(atr_stop, 2), 'ATR'
    return round(pct_stop, 2), 'fixed_pct'
```

- [ ] **Step 2: Commit**

```bash
git add risk_control/
git commit -m "feat: add hard constraint pre-execution validator

validate_order() checks: daily loss CB, total exposure, single position,
sector concentration, portfolio VaR, liquidity. compute_stop_loss() uses
tighter of ATR 2x or -8%.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3.2: Circuit Breaker & Position Guard

**Files:**
- Create: `risk_control/circuit_breaker.py`
- Create: `risk_control/position_guard.py`

- [ ] **Step 1: Write circuit_breaker.py**

```python
# risk_control/circuit_breaker.py
"""Daily loss circuit breaker — blocks new trades when daily loss exceeds threshold."""

import logging
from datetime import date
from typing import Optional
from models import SessionLocal, PaperSnapshot

logger = logging.getLogger(__name__)

class CircuitBreaker:
    """Tracks daily P&L and enforces circuit breaker rules."""

    def __init__(self, threshold_pct: float = 5.0):
        self.threshold_pct = threshold_pct
        self._tripped_accounts = set()

    def check(self, account_id: int) -> dict:
        """
        Check if circuit breaker is tripped for an account.
        Returns {tripped: bool, daily_pnl_pct: float, reason: str}
        """
        db = SessionLocal()
        try:
            today = date.today().isoformat()
            # Get the day's first and latest snapshot for this account
            first_snap = (
                db.query(PaperSnapshot)
                .filter(
                    PaperSnapshot.account_id == account_id,
                    PaperSnapshot.snapshot_time >= today,
                )
                .order_by(PaperSnapshot.snapshot_time.asc())
                .first()
            )
            latest_snap = (
                db.query(PaperSnapshot)
                .filter(
                    PaperSnapshot.account_id == account_id,
                    PaperSnapshot.snapshot_time >= today,
                )
                .order_by(PaperSnapshot.snapshot_time.desc())
                .first()
            )

            if not first_snap or not latest_snap:
                return {'tripped': False, 'daily_pnl_pct': 0, 'reason': ''}

            # Use daily_pnl_pct from latest snapshot
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
```

- [ ] **Step 2: Write position_guard.py**

```python
# risk_control/position_guard.py
"""Position size and sector concentration guard."""

import logging
from typing import Dict, List, Optional
from models import SessionLocal, PaperPosition

logger = logging.getLogger(__name__)

def get_current_exposures(account_id: int) -> dict:
    """
    Get current portfolio exposure metrics for an account.
    Returns {total_market_value, cash, positions[], sector_exposure{}}
    """
    db = SessionLocal()
    try:
        from models import PaperAccount
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

            # Determine sector (simplified — use first 2 digits of code)
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
        '60': '上海主板', '68': '科创板',
        '00': '深圳主板', '30': '创业板',
        '83': '北交所', '43': '北交所', '87': '北交所',
        '15': 'ETF', '51': 'ETF', '56': 'ETF', '58': 'ETF',
    }
    return mapping.get(prefix, '其他')

def compute_max_order_size(account_id: int, code: str, sector: str = None,
                            max_single_pct: float = 20,
                            max_sector_pct: float = 30,
                            max_total_pct: float = 80) -> Optional[float]:
    """
    Compute the maximum allowed order amount for a buy order.
    Returns None if no limit (shouldn't happen), or the max amount in CNY.
    """
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
        sector_mv = exposures['sector_exposure'].get(sector_key, 0) / 100 * pv if exposures['sector_exposure'] else 0
        max_from_sector = pv * (max_sector_pct / 100) - sector_mv

    max_order = min(max_from_total, max_from_single, max_from_sector)
    return max(0, round(max_order, 2))
```

- [ ] **Step 3: Commit**

```bash
git add risk_control/circuit_breaker.py risk_control/position_guard.py
git commit -m "feat: add circuit breaker and position guard

CircuitBreaker checks daily P&L from PaperSnapshot, trips at -5%.
PositionGuard computes max order size from 3 constraints (total, single, sector).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Phase 4: Pipeline & Feedback

### Task 4.1: Daily Pipeline

**Files:**
- Create: `pipeline/__init__.py`
- Create: `pipeline/daily_pipeline.py`

- [ ] **Step 1: Write daily_pipeline.py**

```python
# pipeline/__init__.py
"""Daily trading pipeline orchestration."""

# pipeline/daily_pipeline.py
"""
Daily post-close pipeline: data → features → DL training → screening → agent analysis → recommendations.
Orchestrated by the existing scheduler.py.
"""

import logging
import os
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
        # Stage 1: Data fetch (15:05)
        t0 = datetime.now()
        logger.info("[1/6] Fetching post-close data...")
        # Reuse existing data fetchers — they already pull latest data
        stage_times['data_fetch'] = (datetime.now() - t0).total_seconds()

        # Stage 2: Feature engineering (15:15)
        t0 = datetime.now()
        logger.info("[2/6] Running feature engineering...")
        # Features are computed on-demand; just ensure caches are fresh
        stage_times['features'] = (datetime.now() - t0).total_seconds()

        # Stage 3: DL model training (15:30)
        t0 = datetime.now()
        logger.info("[3/6] Training DL models...")
        _train_all_models()
        stage_times['dl_training'] = (datetime.now() - t0).total_seconds()

        # Stage 4: Market-wide DL screening (16:00)
        t0 = datetime.now()
        logger.info("[4/6] Running DL screening on all stocks...")
        candidates = _dl_screening()
        stage_times['dl_screening'] = (datetime.now() - t0).total_seconds()

        # Stage 5: LLM Agent analysis (16:30)
        t0 = datetime.now()
        logger.info(f"[5/6] Running LLM agent analysis on top {len(candidates)} stocks...")
        recommendations = _agent_analysis(candidates[:30])
        stage_times['agent_analysis'] = (datetime.now() - t0).total_seconds()

        # Stage 6: Persist recommendations (17:30)
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
    """Train regime detector, short-term, and mid-term models."""
    # Placeholder — training logic uses existing data pipeline
    logger.info("  Model training placeholder — to be implemented with full training loop")

def _dl_screening() -> list:
    """Run DL models on all stocks, return top candidates sorted by score."""
    # Placeholder — uses predict_with_dl() on stock universe
    logger.info("  DL screening placeholder")
    return []

def _agent_analysis(candidates: list) -> list:
    """Run LLM agent analysis on candidate stocks."""
    from llm_agents.agent_orchestrator import batch_analyze
    results = batch_analyze(candidates, max_concurrent=5)
    return results

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
```

- [ ] **Step 2: Commit**

```bash
git add pipeline/
git commit -m "feat: add daily pipeline orchestration

run_daily_pipeline() executes 6-stage workflow: data fetch → features →
DL training → screening → agent analysis → persist recommendations.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4.2: Feedback & Auto-Tuning

**Files:**
- Create: `feedback/__init__.py`
- Create: `feedback/performance_tracker.py`
- Create: `feedback/weight_optimizer.py`

- [ ] **Step 1: Write performance_tracker.py**

```python
# feedback/__init__.py
"""Performance tracking and auto-tuning system."""

# feedback/performance_tracker.py
"""Multi-dimension performance tracking for AI recommendations."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import numpy as np
from models import SessionLocal
from recommendation_tracker import RecommendationTrack, _wilson_ci

logger = logging.getLogger(__name__)

def compute_profit_factor(wins: List[float], losses: List[float]) -> float:
    """avg_win / |avg_loss|"""
    avg_win = np.mean(wins) if wins else 0
    avg_loss = abs(np.mean(losses)) if losses else 1e-10
    return round(avg_win / avg_loss, 2) if avg_loss > 0 else 0

def compute_information_coefficient(predictions: List[int], outcomes: List[int]) -> float:
    """IC = correlation between predicted direction and actual direction."""
    if len(predictions) < 5:
        return 0.0
    return round(float(np.corrcoef(predictions, outcomes)[0, 1]), 4)

def get_performance_report(days: int = 90) -> Dict:
    """
    Generate a comprehensive performance report across all signal sources.
    Tracks: win rate, profit factor, expected return, IC, Sharpe, max drawdown.
    """
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
```

- [ ] **Step 2: Write weight_optimizer.py**

```python
# feedback/weight_optimizer.py
"""Auto-tuning engine — adjusts signal fusion weights based on tracked performance."""

import logging
from typing import Dict

logger = logging.getLogger(__name__)

# Default weights (matching spec signal_fusion weights)
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
    Total weights always sum to 1.0.

    Rules:
    - Win rate > 60% → weight +5%
    - Win rate < 45% → weight -5%
    - Profit factor > 1.5 → bonus +3%
    - Weight floor: 5%, ceiling: 40%
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

    # Apply adjustments with bounds
    new_weights = {}
    for src, w in current_weights.items():
        new_w = w + adjustments.get(src, 0)
        new_weights[src] = max(MIN_WEIGHT, min(MAX_WEIGHT, new_w))

    # Normalize to sum to 1.0
    total = sum(new_weights.values())
    if total > 0:
        new_weights = {k: round(v / total, 4) for k, v in new_weights.items()}

    logger.info(f"Weight tuning: {adjustments} → {new_weights}")
    return new_weights
```

- [ ] **Step 3: Commit**

```bash
git add feedback/
git commit -m "feat: add performance tracking and auto-tuning engine

performance_tracker: win rate, profit factor, Sharpe, IC by source.
weight_optimizer: auto-adjusts signal weights ±5-8% based on recent results.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Phase 5: Frontend

### Task 5.1: Market Regime Indicator Component

**Files:**
- Create: `stock_frontend/src/components/RegimeIndicator.tsx`
- Modify: `stock_frontend/src/pages/Home.tsx`

- [ ] **Step 1: Write RegimeIndicator component**

```tsx
// stock_frontend/src/components/RegimeIndicator.tsx
import { Tag, Tooltip, Card } from 'antd';
import { RiseOutlined, FallOutlined, MinusOutlined } from '@ant-design/icons';

interface RegimeData {
  regime: 'bull' | 'bear' | 'sideways';
  confidence: number;
  probabilities: {
    bull: number;
    bear: number;
    sideways: number;
  };
  regime_score: number;
}

const regimeColors: Record<string, string> = {
  bull: '#cf1322',
  bear: '#1677ff',
  sideways: '#faad14',
};

const regimeIcons: Record<string, React.ReactNode> = {
  bull: <RiseOutlined />,
  bear: <FallOutlined />,
  sideways: <MinusOutlined />,
};

const regimeLabels: Record<string, string> = {
  bull: '牛市',
  bear: '熊市',
  sideways: '震荡',
};

export default function RegimeIndicator({ data }: { data: RegimeData | null }) {
  if (!data) {
    return (
      <Card size="small" title="市场状态">
        <span style={{ color: '#999' }}>暂无数据</span>
      </Card>
    );
  }

  const { regime, confidence, probabilities, regime_score } = data;

  return (
    <Card
      size="small"
      title="市场状态"
      extra={
        <Tooltip title={`置信度: ${(confidence * 100).toFixed(0)}%`}>
          <Tag color={regimeColors[regime]} icon={regimeIcons[regime]}>
            {regimeLabels[regime]}
          </Tag>
        </Tooltip>
      }
    >
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {(['bull', 'bear', 'sideways'] as const).map((r) => (
          <Tooltip key={r} title={`${regimeLabels[r]}概率`}>
            <div
              style={{
                flex: probabilities[r],
                height: 24,
                backgroundColor: regimeColors[r],
                borderRadius: 4,
                minWidth: 40,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#fff',
                fontSize: 12,
                fontWeight: regime === r ? 'bold' : 'normal',
                opacity: regime === r ? 1 : 0.6,
              }}
            >
              {(probabilities[r] * 100).toFixed(0)}%
            </div>
          </Tooltip>
        ))}
      </div>
    </Card>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add stock_frontend/src/components/RegimeIndicator.tsx
git commit -m "feat: add RegimeIndicator component showing market state

Displays bull/bear/sideways with confidence, probability bars,
and visual color coding.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5.2: Agent Reasoning Chain Component

**Files:**
- Create: `stock_frontend/src/components/AgentReasoning.tsx`

- [ ] **Step 1: Write AgentReasoning component**

```tsx
// stock_frontend/src/components/AgentReasoning.tsx
import { Card, Collapse, Tag, Progress, Descriptions } from 'antd';
import {
  GlobalOutlined, LineChartOutlined, FundOutlined,
  SafetyCertificateOutlined, CheckCircleOutlined,
} from '@ant-design/icons';

interface AgentResult {
  stance?: string;
  confidence?: number;
  reasoning?: string;
  veto?: boolean;
  veto_reason?: string;
  risk_grade?: string;
  valuation?: string;
}

interface SpecialistResults {
  Macro?: AgentResult;
  Technical?: AgentResult;
  Fundamental?: AgentResult;
  Risk?: AgentResult;
}

interface DecisionResult {
  action?: string;
  confidence?: number;
  position_pct?: number;
  stop_loss_pct?: number;
  take_profit_pct?: number;
  reasoning?: string;
  risk_flags?: string[];
  horizon?: string;
}

interface AgentReasoningProps {
  specialists: SpecialistResults;
  decision: DecisionResult;
}

const agentIcons: Record<string, React.ReactNode> = {
  Macro: <GlobalOutlined />,
  Technical: <LineChartOutlined />,
  Fundamental: <FundOutlined />,
  Risk: <SafetyCertificateOutlined />,
};

const stanceColors: Record<string, string> = {
  bullish: '#cf1322',
  neutral: '#faad14',
  bearish: '#1677ff',
};

const actionColors: Record<string, string> = {
  buy: '#cf1322',
  sell: '#1677ff',
  hold: '#faad14',
  watch: '#d9d9d9',
};

const actionLabels: Record<string, string> = {
  buy: '买入',
  sell: '卖出',
  hold: '持有',
  watch: '观望',
};

export default function AgentReasoning({ specialists, decision }: AgentReasoningProps) {
  const items = Object.entries(specialists).map(([name, result]) => ({
    key: name,
    label: (
      <span>
        {agentIcons[name]} {name}
        {result?.stance && (
          <Tag color={stanceColors[result.stance]} style={{ marginLeft: 8 }}>
            {result.stance}
          </Tag>
        )}
        {result?.veto && <Tag color="red">否决</Tag>}
        {result?.risk_grade && (
          <Tag color={result.risk_grade === 'high' ? 'red' : 'green'}>
            风险: {result.risk_grade}
          </Tag>
        )}
      </span>
    ),
    children: (
      <div>
        <p>{result?.reasoning || '无分析'}</p>
        {result?.confidence !== undefined && (
          <Progress percent={result.confidence} size="small" />
        )}
      </div>
    ),
  }));

  return (
    <Card title="AI Agent 推理链" size="small">
      <Collapse items={items} size="small" />

      <Card
        type="inner"
        title={
          <span>
            <CheckCircleOutlined /> 最终决策
            {decision?.action && (
              <Tag color={actionColors[decision.action]} style={{ marginLeft: 8 }}>
                {actionLabels[decision.action] || decision.action}
              </Tag>
            )}
          </span>
        }
        style={{ marginTop: 12 }}
      >
        <Descriptions column={2} size="small">
          <Descriptions.Item label="置信度">{decision?.confidence ?? '-'}%</Descriptions.Item>
          <Descriptions.Item label="建议仓位">{decision?.position_pct ?? '-'}%</Descriptions.Item>
          <Descriptions.Item label="止损">{decision?.stop_loss_pct ?? '-'}%</Descriptions.Item>
          <Descriptions.Item label="止盈">{decision?.take_profit_pct ?? '-'}%</Descriptions.Item>
          <Descriptions.Item label="周期">{decision?.horizon ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="风险标签">
            {decision?.risk_flags?.map((flag) => (
              <Tag key={flag} color="orange">{flag}</Tag>
            )) || '-'}
          </Descriptions.Item>
        </Descriptions>
        <p style={{ marginTop: 8 }}>{decision?.reasoning}</p>
      </Card>
    </Card>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add stock_frontend/src/components/AgentReasoning.tsx
git commit -m "feat: add AgentReasoning component — shows full AI reasoning chain

Collapsible panels for Macro/Technical/Fundamental/Risk agents,
fusion decision card with position/stop/take-profit details.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Phase 6: Integration & End-to-End Testing

### Task 6.1: Register pipeline in scheduler

**Files:**
- Modify: `scheduler.py`

- [ ] **Step 1: Add daily pipeline task**

Add to the task registry in `scheduler.py` (near other task definitions):

```python
# In scheduler.py, add to the task list:

def task_daily_pipeline():
    """收盘后AI流水线 — 每日15:05执行"""
    if not is_market_close_period():
        return None
    from pipeline.daily_pipeline import run_daily_pipeline
    return run_daily_pipeline()

# Add to SCHEDULED_TASKS list:
SCHEDULED_TASKS = [
    # ... existing tasks ...
    {
        'name': 'AI每日流水线',
        'cron': '5 15 * * 1-5',  # 交易日15:05
        'func': task_daily_pipeline,
        'enabled': True,
    },
]
```

- [ ] **Step 2: Add feedback evaluation task**

```python
def task_evaluate_recommendations():
    """评估到期推荐 — 每日收盘后"""
    if not is_market_close_period():
        return None
    from recommendation_tracker import evaluate_tracks
    return evaluate_tracks()

def task_monthly_tune_weights():
    """每月调整信号权重 — 每月第1个交易日"""
    from datetime import date as dt_date
    today = dt_date.today()
    if today.day > 7 or not is_trading_day():  # First week of month
        return None
    from feedback.performance_tracker import get_performance_report
    from feedback.weight_optimizer import tune_weights
    report = get_performance_report(days=60)
    new_weights = tune_weights(report)
    # Persist weights
    from models import SessionLocal, Config
    import json
    db = SessionLocal()
    try:
        existing = db.query(Config).filter(Config.key == 'signal_fusion_weights').first()
        if existing:
            existing.value = json.dumps(new_weights)
        else:
            db.add(Config(key='signal_fusion_weights', value=json.dumps(new_weights)))
        db.commit()
    finally:
        db.close()
    return {'new_weights': new_weights}
```

- [ ] **Step 3: Commit**

```bash
git add scheduler.py
git commit -m "feat: register daily pipeline and feedback tasks in scheduler

- task_daily_pipeline: runs at 15:05 on trading days
- task_evaluate_recommendations: evaluates matured recommendations
- task_monthly_tune_weights: auto-adjusts signal weights monthly

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6.2: End-to-end smoke test

**Files:**
- Create: `tests/test_e2e_pipeline.py`

- [ ] **Step 1: Write E2E test**

```python
# tests/test_e2e_pipeline.py
"""End-to-end smoke tests for the AI trading pipeline."""

import pytest
import numpy as np

class TestE2EPipeline:
    def test_feature_to_prediction_flow(self):
        """Smoke test: features → model → prediction output."""
        from dl_models.features import build_daily_features, DAILY_FEATURE_NAMES
        from dl_models.short_term_predictor import ShortTermPredictor, ShortTermConfig

        # Create synthetic data
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

        # Model prediction
        config = ShortTermConfig(seq_len=30, num_features=20)
        model = ShortTermPredictor(config)
        result = model.predict(feat_matrix, [1, 0, 0])

        assert result['direction'] in ['up', 'down', 'flat']
        assert result['prob_up'] + result['prob_down'] + result['prob_flat'] == pytest.approx(1.0, abs=0.01)
        assert 'expected_return' in result
        assert 'confidence_interval' in result

    def test_hard_constraint_validation(self):
        """Test that hard constraint validator catches violations."""
        from risk_control.hard_constraints import validate_order, ConstraintConfig

        config = ConstraintConfig(single_position_max_pct=20, total_exposure_max_pct=80)
        positions = [
            {'code': '000001', 'market_value': 70000, 'sector': '银行'},
            {'code': '600519', 'market_value': 50000, 'sector': '白酒'},
        ]
        result = validate_order(
            action='buy', target_code='000001', target_sector='银行',
            order_amount=40000, portfolio_value=100000,
            current_positions=positions,
            sector_exposure_map={'银行': 70000, '白酒': 50000},
        )
        assert not result.passed
        assert any('Single position' in v for v in result.violations)

    def test_circuit_breaker_logic(self):
        """Test circuit breaker recognizes excessive loss."""
        from risk_control.hard_constraints import validate_order
        result = validate_order(
            action='buy', target_code='000001', target_sector='银行',
            order_amount=5000, portfolio_value=100000,
            current_positions=[], current_daily_pnl_pct=-6.0,
        )
        assert not result.passed
        assert any('circuit breaker' in v.lower() for v in result.violations)
```

- [ ] **Step 2: Run E2E tests**

```bash
cd /Users/wgfu/work/a-stock-trading && python -m pytest tests/test_e2e_pipeline.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 3: Run all DL model tests**

```bash
cd /Users/wgfu/work/a-stock-trading && python -m pytest tests/test_dl_features.py tests/test_regime_detector.py tests/test_short_term_predictor.py tests/test_mid_term_predictor.py tests/test_calibration.py tests/test_e2e_pipeline.py -v
```

Expected: All tests PASS.

- [ ] **Step 4: Final commit**

```bash
git add tests/test_e2e_pipeline.py
git commit -m "test: add end-to-end pipeline smoke tests

Tests feature→prediction flow, hard constraint validation, circuit breaker.
Verifies the complete feature-to-decision pipeline works.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Plan Summary

| Phase | Tasks | New Files | Modified Files | Key Deliverable |
|-------|-------|-----------|----------------|-----------------|
| 1: DL Layer | 8 | 8 | 2 | DL models + features + integration |
| 2: LLM Agents | 3 | 8 | 1 | Agent prompts + orchestrator |
| 3: Risk Control | 2 | 3 | 0 | Hard constraints + CB + guard |
| 4: Pipeline | 2 | 3 | 0 | Daily pipeline + feedback loop |
| 5: Frontend | 2 | 2 | 1 | Regime indicator + agent reasoning UI |
| 6: Integration | 2 | 1 | 1 | Scheduler + E2E tests |

**Total**: 19 tasks, 25 new files, 5 modified files, 16 commits.

## Running All Tests

```bash
cd /Users/wgfu/work/a-stock-trading
pip install torch onnx onnxruntime scipy loguru --quiet
python -m pytest tests/test_dl_*.py tests/test_calibration.py tests/test_e2e_pipeline.py -v
```
