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
        self.input_proj = nn.LazyLinear(config.d_model)

    def _project_features(self, x: torch.Tensor) -> torch.Tensor:
        """Project input features to d_model dimension."""
        return self.input_proj(x)

    def forward(self, x: torch.Tensor, mask: Optional[torch.Tensor] = None):
        """x: (B, T, F) — returns dict with logits, probs, regime_idx."""
        B, T, F = x.shape
        x = self._project_features(x)
        cls_tokens = self.cls_token.expand(B, -1, -1)
        x = torch.cat([cls_tokens, x], dim=1)
        x = self.pos_encoding(x)
        x = self.transformer(x, src_key_padding_mask=mask)
        cls_out = x[:, 0, :]
        logits = self.classifier(cls_out)
        probs = torch.softmax(logits, dim=-1)
        regime_idx = torch.argmax(probs, dim=-1)
        return {
            'logits': logits,
            'probs': probs,
            'regime_idx': regime_idx,
        }

    def predict(self, features: np.ndarray) -> Dict:
        """Single-sample prediction. features: (T, F) numpy array."""
        self.eval()
        with torch.no_grad():
            x = torch.from_numpy(features).unsqueeze(0).float()
            out = self.forward(x)
            probs = out['probs'][0].numpy()
            regime_idx = int(out['regime_idx'][0])
            confidence = float(probs[regime_idx])
            regime_score = float(probs[0] - probs[1])  # bull_prob - bear_prob
            return {
                'regime': REGIME_LABELS[regime_idx],
                'confidence': round(confidence, 4),
                'probabilities': {
                    'bull': round(float(probs[0]), 4),
                    'bear': round(float(probs[1]), 4),
                    'sideways': round(float(probs[2]), 4),
                },
                'regime_score': round(regime_score, 4),
            }

    def save(self, path: str):
        torch.save({'model_state': self.state_dict(), 'config': self.config}, path)

    @classmethod
    def load(cls, path: str) -> 'RegimeDetector':
        checkpoint = torch.load(path, map_location='cpu', weights_only=False)
        model = cls(checkpoint['config'])
        model.load_state_dict(checkpoint['model_state'])
        return model
