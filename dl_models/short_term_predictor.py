"""Short-term stock predictor — BiLSTM + MultiHeadAttention (1-5 day horizon)."""

import numpy as np
import torch
import torch.nn as nn
from dataclasses import dataclass
from typing import Dict, List

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

    def __post_init__(self):
        assert (self.hidden_dim * 2) % self.num_heads == 0, (
            f"hidden_dim*2 ({self.hidden_dim * 2}) must be divisible by "
            f"num_heads ({self.num_heads})"
        )

class ShortTermPredictor(nn.Module):
    """BiLSTM + MultiHeadAttention predictor for short-term price direction & return."""

    def __init__(self, config: ShortTermConfig, device: str = 'cpu'):
        super().__init__()
        self.config = config
        self.device = device
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
        Returns direction logits/probs and return mu/sigma.
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

        Note: 'key_drivers' in the returned dict will be populated when
        feature-attribution is implemented. Currently returns an empty list.
        """
        self.eval()
        with torch.no_grad():
            x = torch.from_numpy(features).unsqueeze(0).float().to(self.device)
            regime = torch.tensor([regime_encoding], dtype=torch.float).to(self.device)
            out = self.forward(x, regime)

        probs = out['direction_probs'][0].cpu().numpy()  # [flat, up, down]
        mu = float(out['return_mu'][0, 0])
        sigma = float(out['return_sigma'][0, 0])

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
            'key_drivers': [],  # TODO: populate when feature-attribution is implemented
        }

    def save(self, path: str):
        torch.save({'model_state': self.state_dict(), 'config': self.config}, path)

    @classmethod
    def load(cls, path: str, device: str = 'cpu') -> 'ShortTermPredictor':
        torch.serialization.add_safe_globals([ShortTermConfig])
        checkpoint = torch.load(path, map_location=device, weights_only=True)
        model = cls(checkpoint['config'], device=device)
        model.load_state_dict(checkpoint['model_state'])
        return model
