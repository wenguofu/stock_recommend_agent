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
    # Monotonicity: higher input prob -> higher or equal calibrated prob
    assert calibrated[0] <= calibrated[-1]
