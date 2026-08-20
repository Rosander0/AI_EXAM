"""Object detection, chit geometry filtering, and Authorized Object Learning for SANKET.

CRITICAL INVARIANTS:
1. Phones and chits are instant-alerts (raising critical severity immediately).
2. HARD EXCEPTION: Cell phones are NEVER authorized. Visible during calibration is still a phone.
3. Authorized Object Learning: Permitted equipment on desk during calibration is approved forever;
   objects appearing after calibration are flagged as object_unregistered.
4. Objects unassociated with any candidate (e.g. on empty desk) score nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import time
from typing import Dict, List, Optional, Set, Tuple
import numpy as np

from sanket.calibration import CalibrationState, SeatCalibrator
from sanket.config import ConfigDict
from sanket.device import resolve_device
from sanket.pose import KP, Person
from sanket.rules import RuleFiring
from sanket.seats import Seat, SeatMap


@dataclass
class DetectedObject:
    """Represents a localized object with candidate association and authorization state."""
    class_name: str
    label: str  # "phone" | "paper_chit" | "unregistered" | "approved"
    bbox: Tuple[float, float, float, float]  # (x1, y1, x2, y2)
    conf: float
    associated_seat_id: Optional[str] = None
    associated_wrist: Optional[str] = None  # "left" | "right" | "body"
    authorized: bool = False
    stale: bool = False


class ObjectDetector:
    """YOLO Object Detector with Chit Geometry Filter and Authorized Object Registry."""

    def __init__(self, config: ConfigDict):
        self.config = config
        obj_cfg = config.get("objects", {})
        self.enabled = bool(obj_cfg.get("enabled", True))
        self.weights = obj_cfg.get("weights", "models/yolo11m.pt")
        self.conf = float(obj_cfg.get("conf", 0.35))
        self.detect_every_n = max(1, int(obj_cfg.get("detect_every_n_frames", 5)))
        self.watch_classes: List[str] = obj_cfg.get("watch_classes", ["cell phone", "book", "laptop", "remote"])
        self.never_authorized: Set[str] = set(obj_cfg.get("never_authorized", ["cell phone"]))
        self.max_assoc_ratio = float(obj_cfg.get("max_association_distance_ratio", 0.6))
        self.phone_max_area_ratio = float(obj_cfg.get("phone_max_area_ratio", 0.08))
        self.phone_max_abs_pixels = float(obj_cfg.get("phone_max_abs_pixels", 25000.0))
        self.chit_max_area_ratio = float(obj_cfg.get("chit_max_area_ratio", 0.08))
        self.chit_aspect_range: Tuple[float, float] = tuple(obj_cfg.get("chit_aspect_range", (0.4, 2.5)))

        device_pref = config.get("model", {}).get("device", "auto")
        self.device = resolve_device(device_pref)

        self.model = None
        if self.enabled:
            from ultralytics import YOLO
            self.model = YOLO(self.weights)
            self.model.to(self.device)

        # Per-seat authorized object class registry: seat_id -> Set[class_name]
        self.authorized_registry: Dict[str, Set[str]] = {}

        # Cache of last detected objects for frame-skip / throttle
        self.last_objects: List[DetectedObject] = []
        self.total_chits_checked: int = 0
        self.total_chits_filtered: int = 0

    def detect_and_evaluate(
        self,
        frame_image: np.ndarray,
        frame_index: int,
        t: float,
        seat_assignments: Dict[str, Optional[Person]],
        seat_map: Any,
        calibrators: Dict[str, Any],
        unassigned_persons: Optional[List[Person]] = None,
    ) -> Tuple[List[DetectedObject], List[RuleFiring]]:
        """
        Runs detection (or throttled reuse), performs spatial association,
        checks authorization registry, and generates rule firings.
        """
        if not self.enabled or self.model is None:
            return [], []

        # Throttle detection to every Nth frame
        if (frame_index % self.detect_every_n) != 0 and self.last_objects:
            # Propagate prior detected objects
            stale_objs = []
            for obj in self.last_objects:
                stale_objs.append(
                    DetectedObject(
                        class_name=obj.class_name,
                        label=obj.label,
                        bbox=obj.bbox,
                        conf=obj.conf,
                        associated_seat_id=obj.associated_seat_id,
                        associated_wrist=obj.associated_wrist,
                        authorized=obj.authorized,
                        stale=True,
                    )
                )
            return stale_objs, []

        # Run forward detection
        results = self.model.predict(
            source=frame_image,
            conf=self.conf,
            device=self.device,
            imgsz=800,  # Sweet spot: Fast on CPU while keeping small object detail
            verbose=False,
        )

        detected_objs: List[DetectedObject] = []
        firings: List[RuleFiring] = []

        if not results or len(results) == 0:
            self.last_objects = []
            return detected_objs, firings

        res = results[0]
        boxes = res.boxes
        if boxes is None or len(boxes) == 0:
            self.last_objects = []
            return detected_objs, firings

        xyxy = boxes.xyxy.cpu().numpy()
        confs = boxes.conf.cpu().numpy()
        classes = boxes.cls.int().cpu().numpy()
        names = res.names

        # Build candidate pool (both anchored seats and active candidates)
        candidate_pool: Dict[str, Person] = {}
        for sid, p in seat_assignments.items():
            if p is not None:
                candidate_pool[sid] = p
        if unassigned_persons:
            for p in unassigned_persons:
                label = f"Candidate (ID:{p.track_id})" if p.track_id is not None else "Candidate"
                candidate_pool[label] = p

        for i in range(len(boxes)):
            cls_idx = int(classes[i])
            cls_name = names.get(cls_idx, "unknown")
            b_conf = float(confs[i])
            box = (float(xyxy[i, 0]), float(xyxy[i, 1]), float(xyxy[i, 2]), float(xyxy[i, 3]))

            # Check if class is in watch classes
            if cls_name not in self.watch_classes and cls_name not in ("cell phone", "book", "remote"):
                continue

            # 1. Candidate Association (Associates to closest candidate wrist or body)
            assoc_sid, assoc_wrist, person_obj = self._associate_object(box, candidate_pool)

            # Skip background objects not associated with any candidate (e.g. wall windows, empty desks)
            if assoc_sid is None or person_obj is None:
                continue

            # 2. Geometry Filters
            is_phone = False
            is_chit = False

            if cls_name in ("cell phone", "remote"):
                # Geometric filtering for phones: reject huge wall fixtures/windows or non-phone proportions
                if not self._filter_phone_geometry(box, person_obj):
                    continue
                is_phone = True
                label = "phone"
            elif cls_name == "book":
                self.total_chits_checked += 1
                if self._filter_chit_geometry(box, person_obj):
                    is_chit = True
                    label = "paper_chit"
                else:
                    self.total_chits_filtered += 1
                    continue
            else:
                label = cls_name

            # 3. Check Seat Calibration & Authorized Object Learning
            authorized = False
            cal = calibrators.get(assoc_sid)
            is_calibrating = cal is not None and cal.state == CalibrationState.CALIBRATING

            if is_calibrating:
                # Ingest permitted tools into registry during calibration (EXCEPT cell phones)
                if cls_name not in self.never_authorized and not is_phone:
                    if assoc_sid not in self.authorized_registry:
                        self.authorized_registry[assoc_sid] = set()
                    self.authorized_registry[assoc_sid].add(cls_name)
                    authorized = True
                    label = f"approved_{cls_name}"
            else:
                # Post-calibration evaluation
                if (
                    assoc_sid in self.authorized_registry
                    and cls_name in self.authorized_registry[assoc_sid]
                    and cls_name not in self.never_authorized
                    and not is_phone
                ):
                    authorized = True
                    label = f"approved_{cls_name}"

            # 4. Generate Rule Firings for Unauthorized Items
            if not authorized:
                wrist_desc = f"near {assoc_wrist} wrist" if assoc_wrist != "body" else "on desk"
                if is_phone:
                    reason = f"Prohibited mobile phone detected at {assoc_sid} ({wrist_desc}, conf {b_conf:.2f})"
                    firings.append(
                        RuleFiring(
                            rule="object_phone",
                            points=100.0,
                            confidence=b_conf,
                            reason=reason,
                            t_start=t,
                            t_end=t,
                            seat_id=assoc_sid,
                            track_id=person_obj.track_id if person_obj else None,
                            frame_start=frame_index,
                            frame_end=frame_index,
                        )
                    )
                elif is_chit:
                    reason = f"Prohibited paper/chit detected at {assoc_sid} ({wrist_desc}, conf {b_conf:.2f})"
                    firings.append(
                        RuleFiring(
                            rule="object_chit",
                            points=60.0,
                            confidence=b_conf * 0.8,
                            reason=reason,
                            t_start=t,
                            t_end=t,
                            seat_id=assoc_sid,
                            track_id=person_obj.track_id if person_obj else None,
                            frame_start=frame_index,
                            frame_end=frame_index,
                        )
                    )
                else:
                    reason = f"Unregistered object ({cls_name}) appeared at {assoc_sid} at {int(t//60):02d}:{int(t%60):02d}, not present during calibration"
                    firings.append(
                        RuleFiring(
                            rule="object_unregistered",
                            points=40.0,
                            confidence=b_conf * 0.85,
                            reason=reason,
                            t_start=t,
                            t_end=t,
                            seat_id=assoc_sid,
                            track_id=person_obj.track_id if person_obj else None,
                            frame_start=frame_index,
                            frame_end=frame_index,
                        )
                    )

            detected_objs.append(
                DetectedObject(
                    class_name=cls_name,
                    label=label,
                    bbox=box,
                    conf=b_conf,
                    associated_seat_id=assoc_sid,
                    associated_wrist=assoc_wrist,
                    authorized=authorized,
                    stale=False,
                )
            )

        self.last_objects = detected_objs
        return detected_objs, firings

    def _associate_object(
        self,
        box: Tuple[float, float, float, float],
        candidate_pool: Dict[str, Optional[Person]],
    ) -> Tuple[Optional[str], Optional[str], Optional[Person]]:
        """Associates detected object to the nearest candidate via wrist proximity."""
        ocx = (box[0] + box[2]) / 2.0
        ocy = (box[1] + box[3]) / 2.0

        best_sid = None
        best_wrist = None
        best_person = None
        min_dist = float("inf")

        for sid, p in candidate_pool.items():
            if p is None:
                continue

            p_w = max(1.0, p.bbox[2] - p.bbox[0])
            max_allowed_dist = p_w * self.max_assoc_ratio

            # Check Left Wrist
            if p.kp_visible(KP.LEFT_WRIST):
                lx, ly, _ = p.kp(KP.LEFT_WRIST)
                d_left = math.hypot(lx - ocx, ly - ocy)
                if d_left < min_dist and d_left <= max_allowed_dist:
                    min_dist = d_left
                    best_sid = sid
                    best_wrist = "left"
                    best_person = p

            # Check Right Wrist
            if p.kp_visible(KP.RIGHT_WRIST):
                rx, ry, _ = p.kp(KP.RIGHT_WRIST)
                d_right = math.hypot(rx - ocx, ry - ocy)
                if d_right < min_dist and d_right <= max_allowed_dist:
                    min_dist = d_right
                    best_sid = sid
                    best_wrist = "right"
                    best_person = p

            # If wrists not close, check Candidate Workspace Bounding Box
            if best_wrist is None:
                px1, py1, px2, py2 = p.bbox
                margin = p_w * 0.35
                if (px1 - margin <= ocx <= px2 + margin) and (py1 - margin <= ocy <= py2 + margin):
                    pcx, pcy = p.bbox_center()
                    d_box = math.hypot(pcx - ocx, pcy - ocy)
                    if d_box < min_dist:
                        min_dist = d_box
                        best_sid = sid
                        best_wrist = "desk"
                        best_person = p

            # Fallback to Bounding Box Center
            pcx, pcy = p.bbox_center()
            d_body = math.hypot(pcx - ocx, pcy - ocy)
            if d_body < min_dist and d_body <= max_allowed_dist:
                min_dist = d_body
                best_sid = sid
                best_wrist = "body"
                best_person = p

        return best_sid, best_wrist, best_person

    def _filter_phone_geometry(self, obj_box: Tuple[float, float, float, float], person: Person) -> bool:
        """Filters out huge background objects, wall windows, and non-phone scale boxes."""
        ow = max(1.0, obj_box[2] - obj_box[0])
        oh = max(1.0, obj_box[3] - obj_box[1])
        obj_area = ow * oh

        # 1. Absolute pixel size check (phones in CCTV are never > 25,000 px^2; glass windows on walls are 100,000+ px^2)
        if obj_area > self.phone_max_abs_pixels:
            return False

        # 2. Relative area check (phone is small relative to candidate body, < 8%)
        p_area = person.bbox_area()
        if p_area > 0:
            area_ratio = obj_area / p_area
            if area_ratio > self.phone_max_area_ratio:
                return False

        # 3. Aspect ratio check for smartphones (portrait or landscape)
        # Relaxed to 0.1 - 10.0 to catch slivers of occluded phones
        aspect = ow / oh
        if not (0.1 <= aspect <= 10.0):
            return False

        return True

    def _filter_chit_geometry(self, obj_box: Tuple[float, float, float, float], person: Person) -> bool:
        """Applies area, aspect ratio, and wrist proximity filtering to classify small paper chits."""
        ow = max(1.0, obj_box[2] - obj_box[0])
        oh = max(1.0, obj_box[3] - obj_box[1])
        obj_area = ow * oh

        p_area = person.bbox_area()
        if p_area <= 0:
            return False

        # Area filter: Answer sheet is large (>15% person bbox); chit is small (<8%)
        area_ratio = obj_area / p_area
        if area_ratio > self.chit_max_area_ratio:
            return False

        # Aspect ratio filter: Chit aspect ratio within [0.4, 2.5]
        aspect = ow / oh
        if not (self.chit_aspect_range[0] <= aspect <= self.chit_aspect_range[1]):
            return False

        return True
