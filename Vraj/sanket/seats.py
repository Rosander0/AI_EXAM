"""Seat anchoring and staff classification for SANKET.

CRITICAL INSIGHT:
Exam candidates are stationary and arranged in a grid; generic trackers assume motion.
Identity is anchored to the SEAT, not to the tracker:
- The seat is stable; the track ID is transient.
- Temporary occlusions or tracker ID flips do not reattribute or reset accumulated score.
- Wandering individuals (invigilators) who never occupy a seat or bind to multiple seats
  are classified as STAFF and excluded from candidate scoring and neighbor-reach rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import yaml
import numpy as np

from sanket.config import ConfigDict
from sanket.pose import Person


def compute_iou(boxA: Tuple[float, float, float, float], boxB: Tuple[float, float, float, float]) -> float:
    """Computes Intersection over Union (IoU) between two bounding boxes (xyxy)."""
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    inter_w = max(0.0, xB - xA)
    inter_h = max(0.0, yB - yA)
    inter_area = inter_w * inter_h
    if inter_area <= 0:
        return 0.0

    boxA_area = max(0.0, boxA[2] - boxA[0]) * max(0.0, boxA[3] - boxA[1])
    boxB_area = max(0.0, boxB[2] - boxB[0]) * max(0.0, boxB[3] - boxB[1])
    union_area = boxA_area + boxB_area - inter_area
    if union_area <= 0:
        return 0.0

    return inter_area / union_area


@dataclass
class Seat:
    """Represents an individual monitored exam desk location."""
    seat_id: str  # "S01", "S02", ...
    grid_row: int
    grid_col: int
    anchor_box: Tuple[float, float, float, float]  # (x1, y1, x2, y2)
    current_track_id: Optional[int] = None
    occupied: bool = False
    first_seen_t: float = 0.0
    last_seen_t: float = 0.0
    binding_history: List[int] = field(default_factory=list)

    # Suspicion metrics tracked per seat
    score: float = 0.0
    peak_score: float = 0.0
    event_count: int = 0
    distinct_rules: int = 0
    sustained_seconds: float = 0.0
    calibrated: bool = False
    last_reason: Optional[str] = None


@dataclass
class TrackHistory:
    """Maintains lifespan and seat interaction profile for a single track ID."""
    track_id: int
    first_seen_t: float
    last_seen_t: float
    bound_seats: Set[str] = field(default_factory=set)
    is_staff: bool = False
    first_centroid: Optional[Tuple[float, float]] = None
    max_displacement: float = 0.0


class SeatMap:
    """Manages seat discovery, grid layout, person-to-seat binding, and staff classification."""

    def __init__(self, config: ConfigDict, manual_seats_path: Optional[str | Path] = None):
        self.config = config
        ident_cfg = config.get("identity", {})
        self.discovery_seconds = float(ident_cfg.get("discovery_seconds", 30))
        self.min_seat_persistence = float(ident_cfg.get("min_seat_persistence", 0.6))
        self.row_tolerance_ratio = float(ident_cfg.get("row_tolerance_ratio", 0.15))
        self.min_binding_iou = float(ident_cfg.get("min_binding_iou", 0.3))
        self.seat_release_seconds = float(ident_cfg.get("seat_release_seconds", 20))
        self.staff_grace_seconds = float(ident_cfg.get("staff_grace_seconds", 10))
        self.max_seat_bindings = int(ident_cfg.get("max_seat_bindings", 2))
        self.staff_exclusion_enabled = bool(ident_cfg.get("staff_exclusion_enabled", True))

        self.seats: Dict[str, Seat] = {}
        self.is_discovered: bool = False
        self.discovery_samples: List[Tuple[float, List[Tuple[float, float, float, float]]]] = []
        self.track_histories: Dict[int, TrackHistory] = {}
        self.total_frames_seen: int = 0
        self.frame_height: int = 720
        self.frame_width: int = 1280

        # Load manual seats override if provided
        if manual_seats_path:
            self._load_manual_seats(manual_seats_path)

    def _load_manual_seats(self, path: str | Path) -> None:
        """Loads predefined seat layout from YAML file."""
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(f"Manual seats file not found: {path}")
        with open(p, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        seats_list = data.get("seats", [])
        for item in seats_list:
            sid = item["seat_id"]
            box = tuple(map(float, item["anchor_box"]))
            seat = Seat(
                seat_id=sid,
                grid_row=item.get("grid_row", 0),
                grid_col=item.get("grid_col", 0),
                anchor_box=box,
            )
            self.seats[sid] = seat

        self.is_discovered = True
        print(f"[SEATS] Loaded {len(self.seats)} manual seat anchors from {path}")

    def update(self, persons: List[Person], t: float, frame_shape: Tuple[int, int]) -> Tuple[Dict[str, Optional[Person]], List[Person]]:
        """
        Updates seat bindings for the current frame.
        Returns:
          - Mapping of seat_id -> assigned Person (or None if unoccupied)
          - List of Person instances classified as STAFF
        """
        self.frame_height, self.frame_width = frame_shape[:2]
        self.total_frames_seen += 1

        # Track history lifecycle update
        for p in persons:
            if p.track_id is not None:
                cx, cy = p.bbox_center()
                if p.track_id not in self.track_histories:
                    self.track_histories[p.track_id] = TrackHistory(
                        track_id=p.track_id,
                        first_seen_t=t,
                        last_seen_t=t,
                        first_centroid=(cx, cy),
                        max_displacement=0.0,
                    )
                else:
                    th = self.track_histories[p.track_id]
                    th.last_seen_t = t
                    if th.first_centroid is not None:
                        disp = math.hypot(cx - th.first_centroid[0], cy - th.first_centroid[1])
                        th.max_displacement = max(th.max_displacement, disp)

        # Auto-discovery phase
        if not self.is_discovered:
            boxes = [p.bbox for p in persons if p.bbox_conf >= 0.3]
            self.discovery_samples.append((t, boxes))

            if t >= self.discovery_seconds:
                self._run_auto_discovery()

            if not self.is_discovered:
                # Still discovering: no seats assigned yet
                return {}, []

        # Release seats whose tracks have been missing > seat_release_seconds
        for seat in self.seats.values():
            if seat.occupied and (t - seat.last_seen_t) > self.seat_release_seconds:
                seat.occupied = False
                seat.current_track_id = None

        # Calculate Staff Classification
        # Invariant: Everyone is by default a Candidate.
        # Only true roaming proctors walking aisles across multiple desks in an active room are STAFF.
        staff_persons: List[Person] = []
        candidate_persons: List[Person] = []
        has_active_seated_room = len(self.seats) >= 1 and any(s.occupied for s in self.seats.values())

        for p in persons:
            is_staff = False
            if p.track_id is not None and self.staff_exclusion_enabled and has_active_seated_room:
                th = self.track_histories[p.track_id]

                # Check if person is overlapping an existing seat anchor (seated student)
                is_in_seat = False
                for s in self.seats.values():
                    if compute_iou(s.anchor_box, p.bbox) >= 0.20:
                        is_in_seat = True
                        th.bound_seats.add(s.seat_id)
                        break

                if not is_in_seat:
                    pw = max(1.0, p.bbox[2] - p.bbox[0])
                    ph = max(1.0, p.bbox[3] - p.bbox[1])
                    is_standing = (ph / pw) >= 1.65

                    # Condition 1: Proctor hovering/roaming across multiple candidate desks
                    if len(th.bound_seats) > self.max_seat_bindings:
                        th.is_staff = True
                    # Condition 2: Proctor standing and actively walking aisle across the room
                    elif th.max_displacement >= 50.0 and is_standing and (t - th.first_seen_t) >= self.staff_grace_seconds:
                        th.is_staff = True

                is_staff = th.is_staff

            if is_staff:
                staff_persons.append(p)
            else:
                candidate_persons.append(p)

        # Match candidate persons to seat anchors
        seat_assignments: Dict[str, Optional[Person]] = {sid: None for sid in self.seats}
        available_seats = list(self.seats.values())

        # Greedy matching by IoU
        matches: List[Tuple[float, Seat, Person]] = []
        for seat in available_seats:
            for p in candidate_persons:
                iou = compute_iou(seat.anchor_box, p.bbox)
                if iou >= self.min_binding_iou:
                    matches.append((iou, seat, p))

        # Sort matches descending by IoU
        matches.sort(key=lambda m: m[0], reverse=True)
        assigned_seats: Set[str] = set()
        assigned_persons: Set[int] = set()

        for iou, seat, p in matches:
            p_id = id(p)
            if seat.seat_id in assigned_seats or p_id in assigned_persons:
                continue

            assigned_seats.add(seat.seat_id)
            assigned_persons.add(p_id)
            seat_assignments[seat.seat_id] = p

            # Update seat state
            seat.occupied = True
            seat.last_seen_t = t
            if p.track_id is not None:
                if seat.first_seen_t == 0.0:
                    seat.first_seen_t = t
                if p.track_id not in seat.binding_history:
                    seat.binding_history.append(p.track_id)
                seat.current_track_id = p.track_id

                # Update track profile
                if p.track_id in self.track_histories:
                    self.track_histories[p.track_id].bound_seats.add(seat.seat_id)

        return seat_assignments, staff_persons

    def _run_auto_discovery(self) -> None:
        """Clusters stable person bounding boxes into seat anchors and infers grid coordinates."""
        if not self.discovery_samples:
            return

        total_samples = len(self.discovery_samples)
        all_boxes = [box for _, boxes in self.discovery_samples for box in boxes]
        if not all_boxes:
            return

        # Spatial clustering based on IoU overlap or centroid proximity
        clusters: List[List[Tuple[float, float, float, float]]] = []
        for box in all_boxes:
            matched = False
            bcx = (box[0] + box[2]) / 2.0
            bcy = (box[1] + box[3]) / 2.0
            for cluster in clusters:
                avg_box = (
                    float(np.mean([b[0] for b in cluster])),
                    float(np.mean([b[1] for b in cluster])),
                    float(np.mean([b[2] for b in cluster])),
                    float(np.mean([b[3] for b in cluster])),
                )
                acx = (avg_box[0] + avg_box[2]) / 2.0
                acy = (avg_box[1] + avg_box[3]) / 2.0
                if compute_iou(avg_box, box) >= 0.10 or math.hypot(bcx - acx, bcy - acy) <= 150.0:
                    cluster.append(box)
                    matched = True
                    break
            if not matched:
                clusters.append([box])

        # Filter clusters by minimum persistence
        min_occurrences = max(2, int(total_samples * 0.35))
        valid_clusters = [c for c in clusters if len(c) >= min_occurrences]

        if not valid_clusters:
            self.is_discovered = True
            print("[SEATS] No stationary seat anchors found (open reception / queue area).")
            return

        # Compute centroid and anchor box for each cluster (must be seated candidate proportions)
        cluster_data = []
        for cluster in valid_clusters:
            avg_x1 = float(np.median([b[0] for b in cluster]))
            avg_y1 = float(np.median([b[1] for b in cluster]))
            avg_x2 = float(np.median([b[2] for b in cluster]))
            avg_y2 = float(np.median([b[3] for b in cluster]))
            cw = max(1.0, avg_x2 - avg_x1)
            ch = max(1.0, avg_y2 - avg_y1)
            aspect = ch / cw

            # Seated desk candidates have aspect ratio <= 1.65; standing people at lockers have tall aspect >= 1.75
            # Relaxed to 3.0 to support high camera angles where seated candidates appear very tall
            if aspect >= 3.0:
                continue

            cy = (avg_y1 + avg_y2) / 2.0
            cx = (avg_x1 + avg_x2) / 2.0
            cluster_data.append({
                "box": (avg_x1, avg_y1, avg_x2, avg_y2),
                "cx": cx,
                "cy": cy,
            })

        if not cluster_data:
            self.is_discovered = True
            print("[SEATS] No seated candidate desks found (all detected persons are standing/moving).")
            return

        # Infer Grid: Group by rows (tolerance = row_tolerance_ratio * frame_height)
        row_tol = self.row_tolerance_ratio * self.frame_height
        cluster_data.sort(key=lambda item: item["cy"])

        rows: List[List[dict]] = []
        for item in cluster_data:
            placed = False
            for row in rows:
                row_avg_y = float(np.mean([it["cy"] for it in row]))
                if abs(item["cy"] - row_avg_y) <= row_tol:
                    row.append(item)
                    placed = True
                    break
            if not placed:
                rows.append([item])

        # Sort rows top-to-bottom, columns left-to-right
        rows.sort(key=lambda r: float(np.mean([it["cy"] for it in r])))

        seat_idx = 1
        ascii_lines = ["\nDiscovered Seat Grid:"]

        for r_idx, row in enumerate(rows):
            row.sort(key=lambda it: it["cx"])
            row_symbols = []
            for c_idx, item in enumerate(row):
                sid = f"S{seat_idx:02d}"
                seat = Seat(
                    seat_id=sid,
                    grid_row=r_idx + 1,
                    grid_col=c_idx + 1,
                    anchor_box=item["box"],
                )
                self.seats[sid] = seat
                row_symbols.append(f"[{sid}]")
                seat_idx += 1
            ascii_lines.append("  " + "  ".join(row_symbols))

        self.is_discovered = True
        print("\n".join(ascii_lines) + "\n")
