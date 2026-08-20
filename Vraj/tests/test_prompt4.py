"""Unit tests for SANKET Prompt 4 (Per-Seat Baseline Calibration)."""

import numpy as np
import pytest
from sanket.calibration import CalibrationState, SeatCalibrator
from sanket.config import load_config
from sanket.pose import KP, Person
from sanket.seats import Seat


def create_sample_person(asym_ratio: float = 0.65, shoulder_span_px: float = 120.0, t: float = 0.0) -> Person:
    """Helper creating a person with exact ear-nose asymmetry ratio."""
    kpts = np.zeros((17, 3), dtype=np.float32)
    # Visible shoulders
    kpts[KP.LEFT_SHOULDER] = (100.0, 200.0, 0.9)
    kpts[KP.RIGHT_SHOULDER] = (100.0 + shoulder_span_px, 200.0, 0.9)

    # Place nose and ears to yield exact asymmetry
    # d(L_ear, nose) = 30, d(R_ear, nose) = 30 + asym_ratio * span
    diff = asym_ratio * shoulder_span_px
    kpts[KP.NOSE] = (150.0, 150.0, 0.9)
    kpts[KP.LEFT_EAR] = (120.0, 150.0, 0.9)
    kpts[KP.RIGHT_EAR] = (150.0 + 30.0 + diff, 150.0, 0.9)

    return Person(
        track_id=1,
        bbox=(80.0, 100.0, 250.0, 350.0),
        bbox_conf=0.9,
        keypoints=kpts,
        frame_index=0,
        t=t,
        stale=False,
    )


def test_calibration_rolling_median_resilience_to_early_spike():
    """Verify that a single early movement does not poison the rolling median baseline."""
    cfg = load_config("config.yaml")
    cfg.calibration["min_samples"] = 20
    cfg.calibration["seconds"] = 1.0
    calibrator = SeatCalibrator("S01", cfg)
    seat = Seat("S01", 1, 1, (80.0, 100.0, 250.0, 350.0))

    # Ingest 19 frames of normal resting posture (asymmetry 0.65)
    for i in range(19):
        p = create_sample_person(asym_ratio=0.65, t=i * 0.1)
        calibrator.add_sample(p, seat, t=i * 0.1)

    # Frame 20 is an extreme spike (turned completely around: asymmetry 1.50)
    p_spike = create_sample_person(asym_ratio=1.50, t=1.9)
    calibrator.add_sample(p_spike, seat, t=1.9)

    # Assert calibrator reached CALIBRATED state
    assert calibrator.is_calibrated
    # Rolling median MUST equal 0.65, untouched by the single spike
    base_asym = calibrator.baseline("ear_nose_asymmetry")
    assert base_asym == pytest.approx(0.65, abs=0.01)


def test_deviation_calculation():
    """Verify deviation from baseline normalized by spread (MAD)."""
    cfg = load_config("config.yaml")
    cfg.calibration["min_samples"] = 10
    cfg.calibration["min_spread"] = 0.05
    calibrator = SeatCalibrator("S01", cfg)
    seat = Seat("S01", 1, 1, (80.0, 100.0, 250.0, 350.0))

    for i in range(10):
        p = create_sample_person(asym_ratio=0.65, t=i * 0.1)
        calibrator.add_sample(p, seat, t=i * 0.1)

    assert calibrator.is_calibrated
    # Current value = 0.85 -> deviation = (0.85 - 0.65) / 0.05 = 4.0 MADs
    dev = calibrator.deviation("ear_nose_asymmetry", 0.85)
    assert dev == pytest.approx(4.0, abs=0.1)


def test_drift_freeze_on_high_score():
    """Verify that long-window drift updates freeze when seat suspicion score > drift_freeze_score (30)."""
    cfg = load_config("config.yaml")
    cfg.calibration["min_samples"] = 5
    cfg.calibration["drift_freeze_score"] = 30.0
    calibrator = SeatCalibrator("S01", cfg)
    seat = Seat("S01", 1, 1, (80.0, 100.0, 250.0, 350.0))

    # Calibrate with baseline 0.60
    for i in range(5):
        p = create_sample_person(asym_ratio=0.60, t=i * 0.1)
        calibrator.add_sample(p, seat, t=i * 0.1)

    assert calibrator.is_calibrated

    # Add high-score samples (score = 50.0 > 30.0) with shifted posture (asym = 0.95)
    for i in range(50):
        t = 5.0 + i * 0.1
        p_shifted = create_sample_person(asym_ratio=0.95, t=t)
        calibrator.add_sample(p_shifted, seat, t=t, current_score=50.0)

    # Baseline MUST NOT have absorbed the 0.95 shift (must remain frozen at 0.60)
    assert calibrator.baseline("ear_nose_asymmetry") == pytest.approx(0.60, abs=0.01)
