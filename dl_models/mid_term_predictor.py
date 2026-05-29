# dl_models/mid_term_predictor.py
"""Mid-term stock predictor — Transformer for 1-4 week direction & return."""

import numpy as np
import torch
import torch.nn as nn
from dataclasses import dataclass
from typing import Dict, List
from .regime_detector import PositionalEncoding

DIRECTION_LABELS = {0: 'flat', 1: 'up', 2: 'down'}


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

    def __post_init__(self):
        assert self.d_model % self.num_heads == 0, (
            f"d_model ({self.d_model}) must be divisible by num_heads ({self.num_heads})"
        )


class MidTermPredictor(nn.Module):
    """Transformer-based predictor for 1-4 week stock direction and expected return."""

    def __init__(self, config: MidTermConfig, device: str = 'cpu'):
        super().__init__()
        self.config = config
        self.device = device
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
        """Single-sample prediction."""
        self.eval()
        with torch.no_grad():
            x_p = torch.from_numpy(price_features).unsqueeze(0).float().to(self.device)
            x_f = torch.from_numpy(fund_features).unsqueeze(0).float().to(self.device)
            regime = torch.tensor([regime_encoding], dtype=torch.float).to(self.device)
            out = self.forward(x_p, x_f, regime)
        probs = out['direction_probs'][0].cpu().numpy()
        mu = float(out['return_mu'][0, 0].cpu())
        sigma = float(out['return_sigma'][0, 0].cpu())
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
            'key_drivers': [],
        }

    def save(self, path: str):
        torch.save({'model_state': self.state_dict(), 'config': self.config}, path)

    @classmethod
    def load(cls, path: str, device: str = 'cpu') -> 'MidTermPredictor':
        import torch
        torch.serialization.add_safe_globals([MidTermConfig])
        checkpoint = torch.load(path, map_location=device, weights_only=True)
        model = cls(checkpoint['config'], device=device)
        model.load_state_dict(checkpoint['model_state'])
        return model
