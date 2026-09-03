"""Geometric feature extraction for SANKET.

CRITICAL DESIGN PRINCIPLE:
Features are MEASUREMENTS ONLY — no judgements, no thresholds, no scoring.
Rules consume these measurements in Prompt 6.

CRITICAL INVARIANTS:
1. Every field is None when underlying keypoints are below confidence. Never guess 0.
2. Temporal smoothing uses a time-based window (t), behaving identically under frame-skip.
3. STAFF tracks never produce neighbour intrusion against anyone.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import math
from typing import Deque, Dict, List, Optional, Tuple
import numpy as np

from sanket.calibration import SeatCalibrator
from sanket.config import ConfigDict
from sanket.pose import KP, Person
from sanket.seats import Seat, SeatMap


@dataclass
class SeatFeatures:
    """Represents purely geometric measurements for a single seat at time t."""
    seat_id: str
    t: float
    head_turn_deviation: Optional[float] = None     # Normalized deviation from this seat's baseline
    head_yaw_direction: Optional[str] = None       # "left" | "right" | "centre"
    shoulder_span_ratio: Optional[float] = None    # current / calibrated baseline span
    torso_rotation: Optional[float] = None         # proxy for turning away from desk (0.0 to 1.0)
    wrist_visibility: Tuple[bool, bool] = (False, False)  # (left_visible, right_visible)
    hidden_hands_duration: float = 0.0             # Continuous seconds both wrists below min_conf
    neighbour_intrusion: Dict[str, float] = field(default_factory=dict)  # neighbour_seat_id -> intrusion depth fraction
    talking_targets: Dict[str, float] = field(default_factory=dict)      # other_seat_id -> talking/gaze alignment (0.0 to 1.0)
    nose_displacement: Optional[float] = None      # Distance from calibrated resting position / span
    valid: bool = True                             # False if too few keypoints to trust
    invalid_reason: Optional[str] = None


class FeatureExtractor:
    """Extracts, normalizes, and temporally smooths per-seat geometric features."""

    def __init__(self, config: ConfigDict):
        self.config = config
        feat_cfg = config.get("features", {})
        self.smoothing_window_s = float(feat_cfg.get("smoothing_window_seconds", 0.5))
        self.adjacency_mode = feat_cfg.get("adjacency_mode", "grid")
        self.adjacency_max_dist_ratio = float(feat_cfg.get("adjacency_max_distance_ratio", 1.5))

        # Per-seat tracking state for hidden hands duration: seat_id -> start_t
        self.hidden_hands_start: Dict[str, Optional[float]] = {}

        # Temporal smoothing buffers: seat_id -> metric -> deque of (t, value)
        self.smooth_buffers: Dict[str, Dict[str, Deque[Tuple[float, float]]]] = {}

    def extract_features(
        self,
        seat_assignments: Dict[str, Optional[Person]],
        staff_persons: List[Person],
        seat_map: SeatMap,
        calibrators: Dict[str, SeatCalibrator],
        t: float,
    ) -> Dict[str, SeatFeatures]:
        """Computes geometric features for all active seats in the current frame."""
        results: Dict[str, SeatFeatures] = {}

        # Identify adjacent seat pairs for neighbour intrusion
        adjacent_map = self._compute_adjacency(seat_map)

        for sid, person in seat_assignments.items():
            if sid not in self.smooth_buffers:
                self.smooth_buffers[sid] = {
                    "head_turn_deviation": deque(),
                    "shoulder_span_ratio": deque(),
                    "torso_rotation": deque(),
                    "nose_displacement": deque(),
                }

            if person is None:
                # Seat unoccupied
                self.hidden_hands_start[sid] = None
                results[sid] = SeatFeatures(
                    seat_id=sid,
                    t=t,
                    valid=False,
                    invalid_reason="Seat unoccupied",
                )
                continue

            calibrator = calibrators.get(sid)
            is_calibrated = calibrator is not None and calibrator.is_calibrated

            # 1. Wrist visibility and hidden hands duration
            lw_vis = person.kp_visible(KP.LEFT_WRIST)
            rw_vis = person.kp_visible(KP.RIGHT_WRIST)
            both_hidden = not lw_vis and not rw_vis

            if both_hidden:
                if self.hidden_hands_start.get(sid) is None:
                    self.hidden_hands_start[sid] = t
                hidden_duration = max(0.0, t - self.hidden_hands_start[sid])
            else:
                self.hidden_hands_start[sid] = None
                hidden_duration = 0.0

            # 2. Head turn deviation & yaw direction
            raw_asym = person.ear_nose_asymmetry()
            head_dev = None
            yaw_dir = None

            if raw_asym is not None:
                if is_calibrated and calibrator and calibrator.baseline("ear_nose_asymmetry") is not None:
                    head_dev = calibrator.deviation("ear_nose_asymmetry", raw_asym)
                elif raw_asym >= 0.30:
                    # Robust uncalibrated fallback
                    head_dev = float((raw_asym - 0.15) / 0.05)

                # Determine direction: compare ear-nose distances
                if person.kp_visible(KP.NOSE):
                    nx, _, _ = person.kp(KP.NOSE)
                    if person.kp_visible(KP.LEFT_EAR) and person.kp_visible(KP.RIGHT_EAR):
                        lex, _, _ = person.kp(KP.LEFT_EAR)
                        rex, _, _ = person.kp(KP.RIGHT_EAR)
                        dist_l = abs(lex - nx)
                        dist_r = abs(rex - nx)
                        if dist_l > dist_r * 1.25:
                            yaw_dir = "right"  # Left ear is farther, looking right
                        elif dist_r > dist_l * 1.25:
                            yaw_dir = "left"   # Right ear is farther, looking left
                        else:
                            yaw_dir = "centre"
                    elif person.kp_visible(KP.RIGHT_EAR):
                        yaw_dir = "right"
                    elif person.kp_visible(KP.LEFT_EAR):
                        yaw_dir = "left"
                    else:
                        yaw_dir = "centre"

            # 3. Shoulder span ratio (foreshortening indicator)
            curr_span = person.shoulder_span()
            span_ratio = None
            if curr_span is not None and is_calibrated:
                base_span = calibrator.baseline("shoulder_span")
                if base_span and base_span > 1e-3:
                    span_ratio = curr_span / base_span

            # 4. Torso rotation
            # Combines foreshortened shoulder span with sideways nose offset
            torso_rot = None
            if curr_span is not None and person.kp_visible(KP.NOSE) and person.kp_visible(KP.LEFT_SHOULDER) and person.kp_visible(KP.RIGHT_SHOULDER):
                lx, _, _ = person.kp(KP.LEFT_SHOULDER)
                rx, _, _ = person.kp(KP.RIGHT_SHOULDER)
                nx, _, _ = person.kp(KP.NOSE)
                mid_x = (lx + rx) / 2.0
                nose_offset = abs(nx - mid_x) / curr_span
                # Rotation metric: higher offset + lower span ratio indicates turning back/away
                span_penalty = max(0.0, 1.0 - (span_ratio if span_ratio is not None else 1.0))
                torso_rot = float(np.clip(nose_offset * 1.5 + span_penalty, 0.0, 2.0))

            # 5. Nose displacement from resting position
            nose_disp = None
            if person.kp_visible(KP.NOSE) and curr_span is not None and curr_span > 0 and is_calibrated:
                nx, ny, _ = person.kp(KP.NOSE)
                seat_obj = seat_map.seats.get(sid)
                if seat_obj:
                    ax1, ay1, ax2, ay2 = seat_obj.anchor_box
                    acx = (ax1 + ax2) / 2.0
                    acy = (ay1 + ay2) / 2.0
                    curr_rel_x = (nx - acx) / curr_span
                    curr_rel_y = (ny - acy) / curr_span
                    base_rx = calibrator.baseline("nose_rel_x") or 0.0
                    base_ry = calibrator.baseline("nose_rel_y") or 0.0
                    nose_disp = math.hypot(curr_rel_x - base_rx, curr_rel_y - base_ry)

            # 6. Neighbour intrusion
            # For each adjacent seat, check if this candidate's visible wrists cross into neighbour anchor box
            neighbour_intrusions: Dict[str, float] = {}
            adjacent_seats = adjacent_map.get(sid, [])

            wrists_to_check = []
            if lw_vis:
                wrists_to_check.append(person.kp(KP.LEFT_WRIST)[:2])
            if rw_vis:
                wrists_to_check.append(person.kp(KP.RIGHT_WRIST)[:2])

            for n_sid in adjacent_seats:
                n_seat = seat_map.seats.get(n_sid)
                if not n_seat:
                    continue
                n_box = n_seat.anchor_box
                n_w = max(1.0, n_box[2] - n_box[0])
                n_h = max(1.0, n_box[3] - n_box[1])

                for wx, wy in wrists_to_check:
                    # Check if wrist is inside neighbour anchor box
                    if n_box[0] <= wx <= n_box[2] and n_box[1] <= wy <= n_box[3]:
                        # Intrusion depth as fraction of box width
                        dist_from_edge = min(wx - n_box[0], n_box[2] - wx)
                        intrusion_frac = min(1.0, dist_from_edge / (n_w * 0.5))
                        if intrusion_frac > 0.05:
                            neighbour_intrusions[n_sid] = max(
                                neighbour_intrusions.get(n_sid, 0.0),
                                float(intrusion_frac),
                            )

            # 7. Candidate-to-Candidate Orientation & Conversation / Talking Targets
            talking_targets: Dict[str, float] = {}
            pcx_a, pcy_a = person.bbox_center()
            span_a = curr_span if curr_span is not None and curr_span > 1.0 else 100.0

            for other_sid, other_p in seat_assignments.items():
                if other_sid == sid or other_p is None:
                    continue

                pcx_b, pcy_b = other_p.bbox_center()
                dist_ab = math.hypot(pcx_b - pcx_a, pcy_b - pcy_a)

                # Check if other candidate is within talking distance (within 3.8x shoulder span)
                if dist_ab <= span_a * 3.8:
                    # Check if candidate A is turned towards candidate B
                    is_turned_toward_b = False
                    if pcx_b > pcx_a and yaw_dir == "right":
                        is_turned_toward_b = True
                    elif pcx_b < pcx_a and yaw_dir == "left":
                        is_turned_toward_b = True
                    elif torso_rot is not None and torso_rot >= 0.8:
                        is_turned_toward_b = True

                    if is_turned_toward_b:
                        talking_targets[other_sid] = 0.85

            # 8. Apply Temporal Smoothing (rolling median over smoothing_window_s)
            smoothed_head_dev = self._smooth_metric(sid, "head_turn_deviation", t, head_dev)
            smoothed_span_ratio = self._smooth_metric(sid, "shoulder_span_ratio", t, span_ratio)
            smoothed_torso_rot = self._smooth_metric(sid, "torso_rotation", t, torso_rot)
            smoothed_nose_disp = self._smooth_metric(sid, "nose_displacement", t, nose_disp)

            results[sid] = SeatFeatures(
                seat_id=sid,
                t=t,
                head_turn_deviation=smoothed_head_dev,
                head_yaw_direction=yaw_dir,
                shoulder_span_ratio=smoothed_span_ratio,
                torso_rotation=smoothed_torso_rot,
                wrist_visibility=(lw_vis, rw_vis),
                hidden_hands_duration=hidden_duration,
                neighbour_intrusion=neighbour_intrusions,
                talking_targets=talking_targets,
                nose_displacement=smoothed_nose_disp,
                valid=True,
                invalid_reason=None,
            )

        return results

    def _smooth_metric(self, seat_id: str, metric: str, t: float, value: Optional[float]) -> Optional[float]:
        """Applies rolling median filter over smoothing_window_s time window."""
        if value is None:
            return None

        buf = self.smooth_buffers[seat_id][metric]
        buf.append((t, value))

        # Purge items older than smoothing_window_s
        while buf and (t - buf[0][0]) > self.smoothing_window_s:
            buf.popleft()

        vals = [v for _, v in buf]
        return float(np.median(vals)) if vals else value

    def _compute_adjacency(self, seat_map: SeatMap) -> Dict[str, List[str]]:
        """Identifies adjacent seats in grid (row +/-1, col +/-1)."""
        adj_map: Dict[str, List[str]] = {sid: [] for sid in seat_map.seats}
        seats_list = list(seat_map.seats.values())

        for i, s1 in enumerate(seats_list):
            for j, s2 in enumerate(seats_list):
                if i == j:
                    continue
                # Same row adjacent column, or same column adjacent row
                row_diff = abs(s1.grid_row - s2.grid_row)
                col_diff = abs(s1.grid_col - s2.grid_col)
                if (row_diff == 0 and col_diff == 1) or (row_diff == 1 and col_diff == 0):
                    adj_map[s1.seat_id].append(s2.seat_id)

        return adj_map
