"""Probability calibration for DL model outputs — temperature scaling + isotonic regression."""

import numpy as np
from scipy.optimize import minimize
from sklearn.isotonic import IsotonicRegression


class TemperatureScaler:
    """Temperature scaling for multi-class probability calibration."""

    def __init__(self):
        self.temperature = 1.0

    def fit(self, logits: np.ndarray, labels: np.ndarray):
        """logits: (N, C), labels: (N,) integer class indices."""
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
