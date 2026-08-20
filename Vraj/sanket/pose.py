"""Pose estimation and multi-person tracking for SANKET.

CRITICAL INVARIANTS:
1. Named keypoints only (IntEnum KP). Never index keypoints with bare integers.
2. Missing or low-confidence keypoints return None. Never substitute (0, 0) or guessed values.
3. Exactly ONE model call per inference frame (model.track() handles detection, pose, and tracking).
4. Frame skip changes sampling resolution only; all durations and timing derive from Frame.t.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
import math
from pathlib import Path
import time
from typing import List, Optional, Tuple
import numpy as np

from sanket.config import ConfigDict
from sanket.device import resolve_device
from sanket.source import Frame


class KP(IntEnum):
    """COCO-17 human pose landmark keypoint indices."""
    NOSE = 0
    LEFT_EYE = 1
    RIGHT_EYE = 2
    LEFT_EAR = 3
    RIGHT_EAR = 4
    LEFT_SHOULDER = 5
    RIGHT_SHOULDER = 6
    LEFT_ELBOW = 7
    RIGHT_ELBOW = 8
    LEFT_WRIST = 9
    RIGHT_WRIST = 10
    LEFT_HIP = 11
    RIGHT_HIP = 12
    LEFT_KNEE = 13
    RIGHT_KNEE = 14
    LEFT_ANKLE = 15
    RIGHT_ANKLE = 16


# Standard COCO-17 skeleton limb connectivity pairs
SKELETON_PAIRS: List[Tuple[KP, KP]] = [
    (KP.NOSE, KP.LEFT_EYE),
    (KP.NOSE, KP.RIGHT_EYE),
    (KP.LEFT_EYE, KP.LEFT_EAR),
    (KP.RIGHT_EYE, KP.RIGHT_EAR),
    (KP.LEFT_SHOULDER, KP.RIGHT_SHOULDER),
    (KP.LEFT_SHOULDER, KP.LEFT_ELBOW),
    (KP.RIGHT_SHOULDER, KP.RIGHT_ELBOW),
    (KP.LEFT_ELBOW, KP.LEFT_WRIST),
    (KP.RIGHT_ELBOW, KP.RIGHT_WRIST),
    (KP.LEFT_SHOULDER, KP.LEFT_HIP),
    (KP.RIGHT_SHOULDER, KP.RIGHT_HIP),
    (KP.LEFT_HIP, KP.RIGHT_HIP),
    (KP.LEFT_HIP, KP.LEFT_KNEE),
    (KP.RIGHT_HIP, KP.RIGHT_KNEE),
    (KP.LEFT_KNEE, KP.LEFT_ANKLE),
    (KP.RIGHT_KNEE, KP.RIGHT_ANKLE),
]


@dataclass
class Person:
    """Represents a detected and tracked individual with skeletal landmarks."""
    track_id: Optional[int]
    bbox: Tuple[float, float, float, float]  # (x1, y1, x2, y2)
    bbox_conf: float
    keypoints: np.ndarray  # Shape (17, 3) -> x, y, conf
    frame_index: int
    t: float
    stale: bool = False
    keypoint_min_conf: float = 0.5

    def kp(self, name: KP) -> Tuple[float, float, float]:
        """Returns (x, y, conf) for the specified named keypoint."""
        idx = int(name)
        return float(self.keypoints[idx, 0]), float(self.keypoints[idx, 1]), float(self.keypoints[idx, 2])

    def kp_visible(self, name: KP, min_conf: Optional[float] = None) -> bool:
        """Checks if the keypoint meets or exceeds the required confidence threshold."""
        threshold = self.keypoint_min_conf if min_conf is None else min_conf
        idx = int(name)
        return float(self.keypoints[idx, 2]) >= threshold

    def shoulder_span(self) -> Optional[float]:
        """Computes Euclidean distance between shoulders if both are visible; otherwise None."""
        if not (self.kp_visible(KP.LEFT_SHOULDER) and self.kp_visible(KP.RIGHT_SHOULDER)):
            return None
        lx, ly, _ = self.kp(KP.LEFT_SHOULDER)
        rx, ry, _ = self.kp(KP.RIGHT_SHOULDER)
        return math.hypot(rx - lx, ry - ly)

    def ear_nose_asymmetry(self) -> Optional[float]:
        """
        Computes ear-nose asymmetry normalized by shoulder span:
          |dist(L_ear, nose) - dist(R_ear, nose)| / shoulder_span
        Gracefully handles single-ear occlusion and eye fallback when candidates sit at camera angles.
        Returns None if nose or shoulders are below confidence threshold.
        """
        span = self.shoulder_span()
        if span is None or span <= 1e-4:
            return None

        if not self.kp_visible(KP.NOSE):
            return None

        nx, ny, _ = self.kp(KP.NOSE)

        # 1. Both ears visible
        if self.kp_visible(KP.LEFT_EAR) and self.kp_visible(KP.RIGHT_EAR):
            lex, ley, _ = self.kp(KP.LEFT_EAR)
            rex, rey, _ = self.kp(KP.RIGHT_EAR)
            dist_left = math.hypot(lex - nx, ley - ny)
            dist_right = math.hypot(rex - nx, rey - ny)
            return abs(dist_left - dist_right) / span

        # 2. Single ear visible (occluded profile view from angled camera)
        if self.kp_visible(KP.RIGHT_EAR):
            rex, rey, _ = self.kp(KP.RIGHT_EAR)
            dist_right = math.hypot(rex - nx, rey - ny)
            return dist_right / span

        if self.kp_visible(KP.LEFT_EAR):
            lex, ley, _ = self.kp(KP.LEFT_EAR)
            dist_left = math.hypot(lex - nx, ley - ny)
            return dist_left / span

        # 3. Eyes fallback
        if self.kp_visible(KP.LEFT_EYE) and self.kp_visible(KP.RIGHT_EYE):
            lx, ly, _ = self.kp(KP.LEFT_EYE)
            rx, ry, _ = self.kp(KP.RIGHT_EYE)
            dist_left = math.hypot(lx - nx, ly - ny)
            dist_right = math.hypot(rx - nx, ry - ny)
            return abs(dist_left - dist_right) / span

        return None

    def bbox_center(self) -> Tuple[float, float]:
        """Returns (center_x, center_y) of the bounding box."""
        x1, y1, x2, y2 = self.bbox
        return (x1 + x2) / 2.0, (y1 + y2) / 2.0

    def bbox_area(self) -> float:
        """Returns area in pixels squared."""
        x1, y1, x2, y2 = self.bbox
        return max(0.0, x2 - x1) * max(0.0, y2 - y1)


class PoseEstimator:
    """Manages YOLO pose estimation and tracking in a single forward pass."""

    def __init__(self, config: ConfigDict):
        self.config = config
        model_cfg = config.get("model", {})
        self.pose_weights = model_cfg.get("pose_weights", "models/yolo11m-pose.pt")
        self.imgsz = model_cfg.get("imgsz", 640)
        self.conf = model_cfg.get("conf", 0.25)
        self.keypoint_min_conf = model_cfg.get("keypoint_min_conf", 0.5)
        self.frame_skip = max(1, int(model_cfg.get("frame_skip", 1)))
        self.half = bool(model_cfg.get("half", False))

        device_pref = model_cfg.get("device", "auto")
        self.device = resolve_device(device_pref)

        # Locate tracker config
        tracker_path = Path("sanket/trackers/exam_tracker.yaml")
        if not tracker_path.is_file():
            tracker_path = Path(__file__).parent / "trackers" / "exam_tracker.yaml"
        self.tracker_yaml = str(tracker_path)

        # Initialize YOLO model
        from ultralytics import YOLO
        self.model = YOLO(self.pose_weights)
        self.model.to(self.device)

        self.last_inference_ms: float = 0.0
        self.total_dropped: int = 0
        self._last_persons: List[Person] = []

    def track(self, frame: Frame) -> List[Person]:
        """
        Executes detection, pose estimation, and tracking on the input frame.
        Respects frame_skip by returning previous detections with stale=True.
        """
        # On skipped frames, propagate the prior persons list with updated timestamp
        if (frame.index % self.frame_skip) != 0 and self._last_persons:
            stale_persons = []
            for p in self._last_persons:
                stale_persons.append(
                    Person(
                        track_id=p.track_id,
                        bbox=p.bbox,
                        bbox_conf=p.bbox_conf,
                        keypoints=p.keypoints,
                        frame_index=frame.index,
                        t=frame.t,
                        stale=True,
                        keypoint_min_conf=self.keypoint_min_conf,
                    )
                )
            return stale_persons

        t0 = time.perf_counter()

        track_kwargs = {
            "source": frame.image,
            "persist": True,
            "tracker": self.tracker_yaml,
            "imgsz": self.imgsz,
            "conf": self.conf,
            "device": self.device,
            "verbose": False,
        }
        if self.half:
            track_kwargs["half"] = True

        results = self.model.track(**track_kwargs)

        self.last_inference_ms = (time.perf_counter() - t0) * 1000.0

        persons: List[Person] = []
        if not results or len(results) == 0:
            self._last_persons = []
            return persons

        res = results[0]
        boxes = res.boxes
        keypoints = res.keypoints

        if boxes is None or len(boxes) == 0:
            self._last_persons = []
            return persons

        xyxy = boxes.xyxy.cpu().numpy()
        confs = boxes.conf.cpu().numpy()
        track_ids = boxes.id.int().cpu().numpy() if boxes.id is not None else [None] * len(boxes)

        kpts_data = None
        if keypoints is not None and keypoints.data is not None:
            kpts_data = keypoints.data.cpu().numpy()  # Shape: (N, 17, 3)

        for i in range(len(boxes)):
            b_conf = float(confs[i])
            if b_conf < self.conf:
                self.total_dropped += 1
                continue

            tid = int(track_ids[i]) if track_ids[i] is not None else None
            box = (float(xyxy[i, 0]), float(xyxy[i, 1]), float(xyxy[i, 2]), float(xyxy[i, 3]))

            if kpts_data is not None and i < len(kpts_data):
                kp_arr = kpts_data[i]  # (17, 3)
            else:
                kp_arr = np.zeros((17, 3), dtype=np.float32)

            person = Person(
                track_id=tid,
                bbox=box,
                bbox_conf=b_conf,
                keypoints=kp_arr,
                frame_index=frame.index,
                t=frame.t,
                stale=False,
                keypoint_min_conf=self.keypoint_min_conf,
            )
            persons.append(person)

        self._last_persons = persons
        return persons
