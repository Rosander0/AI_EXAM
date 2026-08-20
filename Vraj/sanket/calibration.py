"""Per-seat baseline self-calibration for SANKET.

THE PROBLEM FIXED:
Fixed global thresholds (e.g. 0.40 ear-asymmetry) generate dozens of phantom
alerts on students sitting at an angle to the camera while sitting perfectly still.

THE SOLUTION:
Every seat is benchmarked against its own resting posture using rolling medians
and Median Absolute Deviation (MAD). Thresholds measure individual deviation
from that student's baseline, not an arbitrary global constant.

CRITICAL INVARIANTS:
1. Rolling median + MAD (never mean) prevents single early movements from poisoning baseline.
2. While CALIBRATING, no scoring events fire.
3. Explicit failure: If calibration fails, mark FAILED and append
   "baseline unavailable, global threshold used" to every reason string.
4. Drift Freeze: Rolling recalibration FREEZES when suspicion score > drift_freeze_score
   so sustained suspicious movements are never absorbed into the baseline as "normal".
"""

from __future__ import annotations

from collections import deque
from enum import Enum
import math
from typing import Deque, Dict, List, Optional, Tuple
import numpy as np

from sanket.config import ConfigDict
from sanket.pose import KP, Person
from sanket.seats import Seat


class CalibrationState(str, Enum):
    CALIBRATING = "CALIBRATING"
    CALIBRATED = "CALIBRATED"
    FAILED = "FAILED"


class SeatCalibrator:
    """Manages baseline learning and deviation scoring for a single seat."""

    def __init__(self, seat_id: str, config: ConfigDict):
        self.seat_id = seat_id
        self.config = config
        cal_cfg = config.get("calibration", {})

        self.calib_seconds = float(cal_cfg.get("seconds", 45))
        self.min_samples = int(cal_cfg.get("min_samples", 200))
        self.min_spread = float(cal_cfg.get("min_spread", 0.02))
        self.drift_enabled = bool(cal_cfg.get("drift_enabled", True))
        self.drift_window_seconds = float(cal_cfg.get("drift_window_seconds", 600))
        self.drift_freeze_score = float(cal_cfg.get("drift_freeze_score", 30))

        self.state = CalibrationState.CALIBRATING
        self.first_sample_t: Optional[float] = None
        self.last_sample_t: Optional[float] = None

        # Sample buffers for calibration phase: deque of (t, value)
        self.samples: Dict[str, List[float]] = {
            "ear_nose_asymmetry": [],
            "shoulder_span": [],
            "nose_rel_x": [],
            "nose_rel_y": [],
            "wrist_visibility": [],
        }

        # Calibrated baselines and spreads (MAD)
        self.baselines: Dict[str, float] = {}
        self.spreads: Dict[str, float] = {}

        # Long-window drift buffers: deque of (t, value)
        self.drift_buffers: Dict[str, Deque[Tuple[float, float]]] = {
            "ear_nose_asymmetry": deque(),
            "shoulder_span": deque(),
            "nose_rel_x": deque(),
            "nose_rel_y": deque(),
        }

    @property
    def is_calibrated(self) -> bool:
        return self.state == CalibrationState.CALIBRATED

    @property
    def is_failed(self) -> bool:
        return self.state == CalibrationState.FAILED

    @property
    def sample_count(self) -> int:
        return len(self.samples["ear_nose_asymmetry"])

    def baseline(self, metric: str) -> Optional[float]:
        """Returns the calibrated baseline value for a given metric."""
        if not self.is_calibrated:
            return None
        return self.baselines.get(metric)

    def has_baseline(self, metric: str) -> bool:
        """Returns True if the calibrator is calibrated and contains the metric baseline."""
        return bool(self.is_calibrated and metric in self.baselines and self.baselines[metric] is not None)

    def spread(self, metric: str) -> float:
        """Returns the calibrated spread (MAD) floored at min_spread."""
        return self.spreads.get(metric, self.min_spread)

    def deviation(self, metric: str, value: float) -> float:
        """
        Calculates normalized deviation from baseline:
          (value - baseline) / spread
        Returns 0.0 if not calibrated or metric missing.
        """
        if not self.is_calibrated or metric not in self.baselines:
            return 0.0
        base = self.baselines[metric]
        spr = self.spread(metric)
        return (value - base) / spr

    def add_sample(self, person: Person, seat: Seat, t: float, current_score: float = 0.0) -> None:
        """
        Ingests a frame measurement.
        During CALIBRATING: builds initial baseline.
        During CALIBRATED: maintains rolling drift updates (unless frozen by high score).
        """
        if self.first_sample_t is None:
            self.first_sample_t = t
        self.last_sample_t = t

        # Extract features for calibration
        asym = person.ear_nose_asymmetry()
        span = person.shoulder_span()

        # Nose position relative to seat anchor center
        nose_rel_x, nose_rel_y = None, None
        if person.kp_visible(KP.NOSE) and span is not None and span > 0:
            nx, ny, _ = person.kp(KP.NOSE)
            ax1, ay1, ax2, ay2 = seat.anchor_box
            acx = (ax1 + ax2) / 2.0
            acy = (ay1 + ay2) / 2.0
            nose_rel_x = (nx - acx) / span
            nose_rel_y = (ny - acy) / span

        # Wrist visibility rate (0.0 to 1.0)
        lw_vis = person.kp_visible(KP.LEFT_WRIST)
        rw_vis = person.kp_visible(KP.RIGHT_WRIST)
        wrist_vis = (1.0 if lw_vis else 0.0) * 0.5 + (1.0 if rw_vis else 0.0) * 0.5

        # 1. Calibration accumulation
        if self.state == CalibrationState.CALIBRATING:
            if asym is not None:
                self.samples["ear_nose_asymmetry"].append(asym)
            if span is not None:
                self.samples["shoulder_span"].append(span)
            if nose_rel_x is not None:
                self.samples["nose_rel_x"].append(nose_rel_x)
                self.samples["nose_rel_y"].append(nose_rel_y)
            self.samples["wrist_visibility"].append(wrist_vis)

            elapsed = t - self.first_sample_t
            valid_samples = len(self.samples["ear_nose_asymmetry"])

            # Check if calibration criteria met
            if valid_samples >= self.min_samples or (elapsed >= self.calib_seconds and valid_samples >= 10):
                self._finalize_calibration()
            elif elapsed >= (self.calib_seconds * 2.0) and valid_samples < 10:
                # Timed out with insufficient visible data
                self.state = CalibrationState.FAILED

        # 2. Rolling drift recalibration (when CALIBRATED)
        elif self.state == CalibrationState.CALIBRATED and self.drift_enabled:
            # CRITICAL DESIGN DECISION:
            # Freeze drift updates while that seat's suspicion score is above drift_freeze_score (30).
            # Otherwise sustained suspicious movements (e.g. repeated sideways peering)
            # would slowly be absorbed into the baseline and become the new "normal".
            if current_score <= self.drift_freeze_score:
                if asym is not None:
                    self._append_drift("ear_nose_asymmetry", t, asym)
                if span is not None:
                    self._append_drift("shoulder_span", t, span)
                if nose_rel_x is not None:
                    self._append_drift("nose_rel_x", t, nose_rel_x)
                    self._append_drift("nose_rel_y", t, nose_rel_y)

    def _append_drift(self, metric: str, t: float, value: float) -> None:
        """Appends value to drift buffer, purges old samples, and updates baseline."""
        buf = self.drift_buffers[metric]
        buf.append((t, value))
        # Purge older than drift_window_seconds
        while buf and (t - buf[0][0]) > self.drift_window_seconds:
            buf.popleft()

        if len(buf) >= 30:
            vals = np.array([v for _, v in buf], dtype=np.float32)
            med = float(np.median(vals))
            mad = float(np.median(np.abs(vals - med)))
            self.baselines[metric] = med
            self.spreads[metric] = max(mad, self.min_spread)

    def _finalize_calibration(self) -> None:
        """Computes rolling median and MAD for all metrics."""
        for metric, vals_list in self.samples.items():
            if len(vals_list) > 0:
                vals = np.array(vals_list, dtype=np.float32)
                med = float(np.median(vals))
                mad = float(np.median(np.abs(vals - med)))
                self.baselines[metric] = med
                self.spreads[metric] = max(mad, self.min_spread)
            else:
                self.baselines[metric] = 0.0
                self.spreads[metric] = self.min_spread

        self.state = CalibrationState.CALIBRATED
