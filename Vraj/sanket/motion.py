"""
Motion Analysis Plugin for SANKET (MOG2 & Optical Flow).
========================================================
Modular, high-speed classical computer vision component providing:
1. MOG2 (Mixture of Gaussians): Background subtraction and seat activity heatmaps.
2. Dense Optical Flow (Farneback): Directional velocity vectors and sudden movement spikes.

This module is 100% plug-and-play and can be safely toggled in config.yaml.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np

from sanket.config import ConfigDict
from sanket.rules import RuleFiring
from sanket.seats import SeatMap


@dataclass
class SeatMotionProfile:
    """Motion metrics for a specific monitored seat."""
    seat_id: str
    motion_energy: float  # Percentage of moving pixels (0.0 - 1.0)
    avg_velocity_px_s: float  # Average pixel velocity from optical flow
    is_spike: bool  # True if rapid motion spurt detected


class MotionAnalyzer:
    """Fast, zero-GPU motion analysis combining MOG2 and Optical Flow."""

    def __init__(self, config: ConfigDict):
        self.config = config
        motion_cfg = config.get("motion", {})
        self.enabled = bool(motion_cfg.get("enabled", False))
        self.mode = motion_cfg.get("mode", "mog2")  # "mog2" | "optical_flow" | "both"
        self.energy_threshold = float(motion_cfg.get("energy_threshold", 0.30))
        self.velocity_spike_threshold = float(motion_cfg.get("velocity_spike_threshold", 45.0))
        self.downsample_width = int(motion_cfg.get("downsample_width", 640))

        # MOG2 Subtractor initialization
        self.mog2 = None
        if self.mode in ("mog2", "both"):
            var_thresh = float(motion_cfg.get("mog2_var_threshold", 16.0))
            detect_shadows = bool(motion_cfg.get("mog2_detect_shadows", False))
            self.mog2 = cv2.createBackgroundSubtractorMOG2(
                history=300,
                varThreshold=var_thresh,
                detectShadows=detect_shadows,
            )

        # Optical Flow state
        self.prev_gray: Optional[np.ndarray] = None
        self.last_t: Optional[float] = None
        self.last_profiles: Dict[str, SeatMotionProfile] = {}

    def analyze_frame(
        self,
        frame_bgr: np.ndarray,
        seat_map: SeatMap,
        t: float,
        frame_index: int = 0,
    ) -> Tuple[Dict[str, SeatMotionProfile], List[RuleFiring]]:
        """
        Analyzes the current frame for foreground motion and optical flow velocities.
        Returns per-seat motion profiles and any detected motion rule firings.
        """
        if not self.enabled:
            return {}, []

        h, w = frame_bgr.shape[:2]
        scale = 1.0

        # Downsample for ultra-fast CPU processing
        if self.downsample_width and w > self.downsample_width:
            scale = self.downsample_width / float(w)
            small_w = self.downsample_width
            small_h = int(round(h * scale))
            proc_bgr = cv2.resize(frame_bgr, (small_w, small_h), interpolation=cv2.INTER_AREA)
        else:
            proc_bgr = frame_bgr

        gray = cv2.cvtColor(proc_bgr, cv2.COLOR_BGR2GRAY)
        dt = (t - self.last_t) if self.last_t is not None else (1.0 / 25.0)
        self.last_t = t

        # 1. Compute MOG2 Foreground Mask
        fg_mask = None
        if self.mog2 is not None:
            fg_mask = self.mog2.apply(proc_bgr)
            # Morphological noise cleanup
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)

        # 2. Compute Dense Optical Flow (Farneback)
        flow = None
        if self.mode in ("optical_flow", "both") and self.prev_gray is not None:
            flow = cv2.calcOpticalFlowFarneback(
                self.prev_gray,
                gray,
                None,
                pyr_scale=0.5,
                levels=2,
                winsize=15,
                iterations=2,
                poly_n=5,
                poly_sigma=1.1,
                flags=0,
            )

        self.prev_gray = gray

        # 3. Evaluate per-seat ROIs
        profiles: Dict[str, SeatMotionProfile] = {}
        firings: List[RuleFiring] = []

        for sid, seat in seat_map.seats.items():
            ax1, ay1, ax2, ay2 = seat.anchor_box
            # Scale anchor box to downsampled coordinates
            sx1 = max(0, int(ax1 * scale))
            sy1 = max(0, int(ay1 * scale))
            sx2 = min(proc_bgr.shape[1], int(ax2 * scale))
            sy2 = min(proc_bgr.shape[0], int(ay2 * scale))

            if sx2 <= sx1 or sy2 <= sy1:
                continue

            roi_area = max(1.0, (sx2 - sx1) * (sy2 - sy1))

            # Measure MOG2 Foreground Energy
            energy = 0.0
            if fg_mask is not None:
                roi_fg = fg_mask[sy1:sy2, sx1:sx2]
                active_pixels = cv2.countNonZero(roi_fg)
                energy = float(active_pixels / roi_area)

            # Measure Optical Flow Velocity Magnitude
            avg_vel = 0.0
            if flow is not None:
                roi_flow = flow[sy1:sy2, sx1:sx2]
                mag, _ = cv2.cartToPolar(roi_flow[..., 0], roi_flow[..., 1])
                # Convert displacement to velocity (pixels/sec)
                avg_vel = float(np.mean(mag) / max(0.01, dt) / scale)

            is_spike = (energy >= self.energy_threshold) or (avg_vel >= self.velocity_spike_threshold)

            prof = SeatMotionProfile(
                seat_id=sid,
                motion_energy=round(energy, 3),
                avg_velocity_px_s=round(avg_vel, 1),
                is_spike=is_spike,
            )
            profiles[sid] = prof

            # Optional rule firing for sudden erratic motion spurts
            if is_spike and seat.occupied:
                reason = f"Abnormal rapid motion detected at {sid} (Energy: {energy*100:.1f}%, Velocity: {avg_vel:.1f}px/s)"
                firings.append(
                    RuleFiring(
                        rule="motion_spurt",
                        points=20.0,
                        confidence=0.75,
                        reason=reason,
                        t_start=t,
                        t_end=t,
                        seat_id=sid,
                        track_id=seat.current_track_id,
                        frame_start=frame_index,
                        frame_end=frame_index,
                    )
                )

        self.last_profiles = profiles
        return profiles, firings
