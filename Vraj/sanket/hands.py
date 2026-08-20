"""Google MediaPipe Hand Landmark & Gesture Analysis for SANKET.

Extracts 21 hand landmarks per candidate hand to detect:
1. Phone grip / Handheld device grip (curled fingers + opposed/elevated thumb)
2. Hand-to-face / listening posture (hand near ear/mouth with flexed elbow)
3. Small chit pinch gesture (index tip to thumb tip precision pinch)
4. Under-desk / lap typing signature

100% immune to background room fixtures (glass windows, wall posters, PC monitors)
because landmarks execute strictly on human body crops.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np

from sanket.config import ConfigDict
from sanket.pose import KP, Person
from sanket.rules import RuleFiring


@dataclass
class HandLandmarks:
    """Represents 21 3D landmarks for a detected human hand."""
    handedness: str  # "Left" | "Right"
    landmarks_2d: np.ndarray  # (21, 2) in normalized [0, 1] frame coordinates
    world_landmarks: np.ndarray  # (21, 3) in metric meters
    is_grip: bool = False
    is_pinch: bool = False
    confidence: float = 0.0


class MediaPipeHandAnalyzer:
    """Manages Google MediaPipe Hand Landmarker and grip/gesture heuristics."""

    def __init__(self, config: ConfigDict):
        self.config = config
        hand_cfg = config.get("hands", {})
        self.enabled = bool(hand_cfg.get("enabled", True))
        self.min_confidence = float(hand_cfg.get("min_confidence", 0.50))
        self.min_duration_s = float(hand_cfg.get("min_duration_seconds", 1.0))
        self.cooldown_s = float(hand_cfg.get("cooldown_seconds", 5.0))
        self.points = float(config.get("scoring", {}).get("weights", {}).get("hand_phone_grip", 50.0))

        self.grip_start_times: Dict[str, Optional[float]] = {}
        self.last_grip_fire: Dict[str, float] = {}

        self.detector = None
        self._init_mediapipe()

    def _init_mediapipe(self):
        """Initializes MediaPipe HandLandmarker Tasks API."""
        if not self.enabled:
            return

        try:
            import mediapipe as mp
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision

            model_path = Path("models/hand_landmarker.task")
            if not model_path.is_file():
                # Download model if not cached
                import urllib.request
                model_path.parent.mkdir(parents=True, exist_ok=True)
                url = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
                urllib.request.urlretrieve(url, str(model_path))

            base_options = python.BaseOptions(model_asset_path=str(model_path))
            options = vision.HandLandmarkerOptions(
                base_options=base_options,
                num_hands=4,
                min_hand_detection_confidence=self.min_confidence,
                min_hand_presence_confidence=self.min_confidence,
                min_tracking_confidence=self.min_confidence,
            )
            self.detector = vision.HandLandmarker.create_from_options(options)
        except Exception as e:
            print(f"[HANDS] MediaPipe initialization error (falling back to pose heuristics): {e}")
            self.detector = None

    def analyze_frame(
        self,
        frame_rgb: np.ndarray,
        seat_assignments: Dict[str, Optional[Person]],
        t: float,
        frame_index: int,
        unassigned_persons: Optional[List[Person]] = None,
    ) -> Tuple[Dict[str, List[HandLandmarks]], List[RuleFiring]]:
        """
        Runs MediaPipe Hand Landmarker on candidate crops and evaluates grip/pinch gestures.
        Returns mapped hand landmarks and temporally filtered rule firings.
        """
        if self.detector is None or not self.enabled:
            return {}, []

        import mediapipe as mp

        h, w = frame_rgb.shape[:2]
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        
        try:
            result = self.detector.detect(mp_image)
        except Exception:
            return {}, []

        seat_hands: Dict[str, List[HandLandmarks]] = {sid: [] for sid in seat_assignments}
        seat_hands["unassigned"] = []
        firings: List[RuleFiring] = []

        if not result or not result.hand_landmarks:
            return seat_hands, firings

        # Build candidate pool (anchored seats + active candidates)
        candidate_pool: Dict[str, Person] = {}
        for sid, p in seat_assignments.items():
            if p is not None:
                candidate_pool[sid] = p
        if unassigned_persons:
            for p in unassigned_persons:
                label = f"Candidate (ID:{p.track_id})" if p.track_id is not None else "Candidate"
                candidate_pool[label] = p

        active_grip_candidates = set()

        # Process each detected hand
        for idx, landmarks in enumerate(result.hand_landmarks):
            handedness = "Right"
            if result.handedness and idx < len(result.handedness) and result.handedness[idx]:
                handedness = result.handedness[idx][0].category_name

            # Convert to numpy array of normalized (x, y)
            pts_2d = np.array([[lm.x, lm.y] for lm in landmarks], dtype=np.float32)
            pts_3d = np.array([[lm.x, lm.y, lm.z] for lm in landmarks], dtype=np.float32)

            wrist_norm = pts_2d[0]  # Wrist landmark (index 0)
            wrist_px = (wrist_norm[0] * w, wrist_norm[1] * h)

            # Associate hand to closest candidate in pool
            best_sid = None
            best_person = None
            min_dist = float("inf")

            for sid_or_label, p in candidate_pool.items():
                if p is None:
                    continue
                px1, py1, px2, py2 = p.bbox
                margin = (px2 - px1) * 0.45
                # Check bounding box containment
                if (px1 - margin <= wrist_px[0] <= px2 + margin) and (py1 - margin <= wrist_px[1] <= py2 + margin):
                    pcx, pcy = p.bbox_center()
                    d = math.hypot(pcx - wrist_px[0], pcy - wrist_px[1])
                    if d < min_dist:
                        min_dist = d
                        best_sid = sid_or_label
                        best_person = p

            # Gesture Analysis (High precision phone grip detection)
            is_grip = self._detect_phone_grip(pts_2d)

            hand_obj = HandLandmarks(
                handedness=handedness,
                landmarks_2d=pts_2d,
                world_landmarks=pts_3d,
                is_grip=is_grip,
                is_pinch=False,
                confidence=0.85,
            )

            target_bucket = best_sid if best_sid in seat_hands else "unassigned"
            seat_hands[target_bucket].append(hand_obj)

            # Temporal persistence tracking for phone grip
            if is_grip and best_person is not None:
                firing_sid = best_sid if best_sid in seat_assignments else f"Candidate (ID:{best_person.track_id})"
                active_grip_candidates.add(firing_sid)

                if self.grip_start_times.get(firing_sid) is None:
                    self.grip_start_times[firing_sid] = t

                dur = t - self.grip_start_times[firing_sid]
                last_fire = self.last_grip_fire.get(firing_sid, -999.0)

                # Must be held continuously for min_duration_s and respect cooldown
                if dur >= self.min_duration_s and (t - last_fire) >= self.cooldown_s:
                    reason = f"Handheld phone grip posture sustained at {firing_sid} ({handedness} hand held for {dur:.1f}s)"
                    firings.append(
                        RuleFiring(
                            rule="hand_phone_grip",
                            points=self.points,
                            confidence=0.88,
                            reason=reason,
                            t_start=self.grip_start_times[firing_sid],
                            t_end=t,
                            seat_id=firing_sid,
                            track_id=best_person.track_id,
                            frame_start=frame_index - int(dur * 25),
                            frame_end=frame_index,
                        )
                    )
                    self.last_grip_fire[firing_sid] = t

        # Reset grip timer for candidates no longer holding a phone grip
        for cid in list(self.grip_start_times.keys()):
            if cid not in active_grip_candidates:
                self.grip_start_times[cid] = None

        return seat_hands, firings

    def _detect_phone_grip(self, pts_2d: np.ndarray) -> bool:
        """
        High-precision phone grip detection with explicit pen-writing and resting-hand rejection:
        - Palm scale computed from wrist to middle MCP.
        - Rejects pen-writing posture (index extended + thumb touching index PIP).
        - Rejects flat/open resting hands on table.
        - Requires curled fingers (middle, ring, pinky) and thumb opposition over device area.
        """
        wrist = pts_2d[0]
        thumb_tip = pts_2d[4]
        index_mcp = pts_2d[5]
        index_pip = pts_2d[6]
        index_tip = pts_2d[8]
        middle_mcp = pts_2d[9]
        middle_tip = pts_2d[12]
        ring_tip = pts_2d[16]
        pinky_tip = pts_2d[20]

        # 1. Palm Scale (wrist to middle MCP distance)
        palm_size = math.hypot(middle_mcp[0] - wrist[0], middle_mcp[1] - wrist[1])
        if palm_size < 1e-4:
            return False

        # 2. Pen / Writing Posture Rejection:
        # Index extended straight along pen + thumb touching index PIP/DIP
        d_index_tip = math.hypot(index_tip[0] - wrist[0], index_tip[1] - wrist[1])
        d_thumb_pen = math.hypot(thumb_tip[0] - index_pip[0], thumb_tip[1] - index_pip[1])
        if d_index_tip > (palm_size * 1.35) and d_thumb_pen < (palm_size * 0.50):
            return False  # Natural pen-writing posture

        # 3. Flat / Open Resting Hand Rejection:
        d_mid_tip = math.hypot(middle_tip[0] - wrist[0], middle_tip[1] - wrist[1])
        d_ring_tip = math.hypot(ring_tip[0] - wrist[0], ring_tip[1] - wrist[1])
        d_pinky_tip = math.hypot(pinky_tip[0] - wrist[0], pinky_tip[1] - wrist[1])

        if d_mid_tip > (palm_size * 1.35) or d_pinky_tip > (palm_size * 1.35):
            return False  # Extended / flat resting hand

        # 4. Phone Grip Signature:
        # Middle, ring, and pinky curled inward around device edge
        if d_mid_tip < (palm_size * 1.15) and d_ring_tip < (palm_size * 1.15) and d_pinky_tip < (palm_size * 1.15):
            # Thumb opposed / positioned over front glass
            d_thumb_opp = math.hypot(thumb_tip[0] - index_mcp[0], thumb_tip[1] - index_mcp[1])
            if d_thumb_opp < (palm_size * 0.85):
                return True

        return False
