"""PyTorch to ONNX conversion utilities for DL prediction models."""

import torch
import numpy as np
from pathlib import Path
from typing import Optional
from .regime_detector import RegimeDetector
from .short_term_predictor import ShortTermPredictor
from .mid_term_predictor import MidTermPredictor


def export_regime_detector(model: RegimeDetector, output_path: str,
                            sample_input: Optional[np.ndarray] = None):
    """Export RegimeDetector to ONNX format."""
    import onnx
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
    onnx_model = onnx.load(output_path)
    onnx.checker.check_model(onnx_model)


def export_short_term(model: ShortTermPredictor, output_path: str,
                       sample_features: Optional[np.ndarray] = None,
                       sample_regime: Optional[np.ndarray] = None):
    """Export ShortTermPredictor to ONNX format."""
    import onnx
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
    onnx_model = onnx.load(output_path)
    onnx.checker.check_model(onnx_model)


def export_mid_term(model: MidTermPredictor, output_path: str,
                     sample_price: Optional[np.ndarray] = None,
                     sample_fund: Optional[np.ndarray] = None,
                     sample_regime: Optional[np.ndarray] = None):
    """Export MidTermPredictor to ONNX format."""
    import onnx
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
    onnx_model = onnx.load(output_path)
    onnx.checker.check_model(onnx_model)


def export_all(models_dir: str = 'model_checkpoints', output_dir: str = 'model_checkpoints'):
    """Export all .pt models in models_dir to ONNX format."""
    models_dir = Path(models_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for pt_file in models_dir.glob('*.pt'):
        if 'regime' in pt_file.name:
            model = RegimeDetector.load(str(pt_file))
            export_regime_detector(model, str(output_dir / (pt_file.stem + '.onnx')))
        elif 'short' in pt_file.name:
            model = ShortTermPredictor.load(str(pt_file))
            export_short_term(model, str(output_dir / (pt_file.stem + '.onnx')))
        elif 'mid' in pt_file.name:
            model = MidTermPredictor.load(str(pt_file))
            export_mid_term(model, str(output_dir / (pt_file.stem + '.onnx')))
