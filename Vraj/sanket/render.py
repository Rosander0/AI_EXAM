"""Frame rendering and visual overlays for SANKET.

CRITICAL INVARIANTS:
1. ALL frame drawing lives in this module. Nothing else draws.
2. Limbs drawn ONLY if BOTH endpoints exceed keypoint_min_conf.
3. Fixed-width HUD overlays prevent layout jitter.
4. Objects rendered with distinct styling, seat connection lines, and [APPROVED] badges.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np

from sanket.calibration import CalibrationState, SeatCalibrator
from sanket.detection import DetectedObject
from sanket.features import SeatFeatures
from sanket.pose import KP, Person, SKELETON_PAIRS
from sanket.seats import Seat, SeatMap


def format_source_time(seconds: float) -> str:
    """Formats timestamp in seconds to MM:SS.mmm format."""
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{mins:02d}:{secs:02d}.{millis:03d}"


def get_status_color(score: float) -> Tuple[int, int, int]:
    """Returns BGR color for status: calm / accumulating / alert."""
    if score >= 100.0:
        return (61, 69, 196)   # Alert #C4453D in BGR -> (61, 69, 196)
    elif score >= 40.0:
        return (58, 135, 200)  # Accum #C8873A in BGR -> (58, 135, 200)
    else:
        return (94, 122, 62)   # Calm #3E7A5E in BGR -> (94, 122, 62)


def draw_hud(frame: np.ndarray, info: Dict[str, Any]) -> np.ndarray:
    """Draws a compact, fixed-width top-left HUD overlay on the frame."""
    frame_index = info.get("frame_index", 0)
    source_t = info.get("t", 0.0)
    fps = info.get("fps", 0.0)
    source_name = info.get("source_name", "Stream")
    device = info.get("device", "CPU")
    frame_skip = info.get("frame_skip", 1)
    people_count = info.get("people_count", 0)
    inference_ms = info.get("inference_ms", 0.0)
    seats_tracked = info.get("seats_tracked", 0)
    seats_total = info.get("seats_total", 0)
    calib_count = info.get("calib_count", 0)
    alerts_total = info.get("alerts_total", 0)
    objects_count = info.get("objects_count", 0)

    time_str = format_source_time(source_t)
    line1 = f"F: {frame_index:06d} | T: {time_str} | SEATS: {seats_tracked:02d}/{seats_total:02d} | CALIB: {calib_count:02d}/{seats_total:02d} | ALERTS: {alerts_total:02d}"
    line2 = f"FPS: {fps:5.1f} | INF: {inference_ms:4.1f}ms | DEV: {device.upper():<3} | OBJS: {objects_count:02d} | SRC: {source_name[:12]:<12}"

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.43
    font_thickness = 1
    line_type = cv2.LINE_AA

    padding = 8
    x1, y1 = 10, 10
    box_w = 600
    box_h = 54
    x2, y2 = x1 + box_w, y1 + box_h

    img_h, img_w = frame.shape[:2]
    x2 = min(x2, img_w - 5)
    y2 = min(y2, img_h - 5)

    overlay = frame.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), (15, 27, 45), -1)  # #0F1B2D ink
    cv2.rectangle(overlay, (x1, y1), (x2, y2), (36, 56, 79), 1)   # #24384F hairline
    cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)

    text_color = (232, 237, 243)
    cv2.putText(frame, line1, (x1 + padding, y1 + 20), font, font_scale, text_color, font_thickness, line_type)
    cv2.putText(frame, line2, (x1 + padding, y1 + 40), font, font_scale, (124, 143, 166), font_thickness, line_type)

    return frame


def draw_seat_anchors(
    frame: np.ndarray,
    seats: Dict[str, Seat],
    calibrators: Optional[Dict[str, SeatCalibrator]] = None,
) -> np.ndarray:
    """Renders static seat anchor boundary boxes with seat tags and score status."""
    for sid, seat in seats.items():
        x1, y1, x2, y2 = map(int, seat.anchor_box)
        cal = calibrators.get(sid) if calibrators else None

        status_col = get_status_color(seat.score)

        if cal and cal.state == CalibrationState.CALIBRATING:
            anchor_color = (60, 120, 160)
            badge_text = f"[{sid}: CALIB {cal.sample_count}]"
        elif cal and cal.state == CalibrationState.FAILED:
            anchor_color = (60, 60, 180)
            badge_text = f"[{sid}: FAIL]"
        else:
            anchor_color = status_col if seat.occupied else (80, 100, 120)
            badge_text = f"[{sid} | {seat.score:4.1f}]"

        cv2.rectangle(frame, (x1, y1), (x2, y2), anchor_color, 1, cv2.LINE_4)
        cv2.putText(frame, badge_text, (x1 + 4, y2 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.36, anchor_color, 1, cv2.LINE_AA)
    return frame


def draw_features_overlay(
    frame: np.ndarray,
    seat_features: Dict[str, SeatFeatures],
    seats: Dict[str, Seat],
) -> np.ndarray:
    """Renders live metric mini-bars next to each seat."""
    for sid, feat in seat_features.items():
        seat = seats.get(sid)
        if not seat or not feat.valid:
            continue

        x1, y1, x2, y2 = map(int, seat.anchor_box)
        bx = max(5, x1 - 110)
        by = y1 + 10

        panel_w = 100
        panel_h = 60
        overlay = frame.copy()
        cv2.rectangle(overlay, (bx, by), (bx + panel_w, by + panel_h), (15, 27, 45), -1)
        cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

        dev = feat.head_turn_deviation if feat.head_turn_deviation is not None else 0.0
        bar_len = int(np.clip(dev * 10, 0, 80))
        bar_col = (58, 135, 200) if dev > 2.0 else (62, 122, 94)
        cv2.putText(frame, f"DEV: {dev:.1f}x", (bx + 2, by + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (200, 200, 200), 1)
        cv2.line(frame, (bx + 2, by + 18), (bx + 2 + bar_len, by + 18), bar_col, 3)

        hh_dur = feat.hidden_hands_duration
        hh_col = (60, 60, 200) if hh_dur >= 3.0 else (120, 140, 160)
        cv2.putText(frame, f"HANDS: {hh_dur:.1f}s", (bx + 2, by + 34), cv2.FONT_HERSHEY_SIMPLEX, 0.32, hh_col, 1)

        span_r = feat.shoulder_span_ratio if feat.shoulder_span_ratio is not None else 1.0
        cv2.putText(frame, f"SPAN: {span_r:.2f}", (bx + 2, by + 50), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (180, 180, 180), 1)

        # Draw Candidate-to-Candidate Conversation / Gaze Vector
        if feat.talking_targets:
            ax1, ay1, ax2, ay2 = map(int, seat.anchor_box)
            acx = (ax1 + ax2) // 2
            acy = (ay1 + ay2) // 2
            for target_sid, score in feat.talking_targets.items():
                if target_sid in seats:
                    tx1, ty1, tx2, ty2 = map(int, seats[target_sid].anchor_box)
                    tcx = (tx1 + tx2) // 2
                    tcy = (ty1 + ty2) // 2
                    cv2.line(frame, (acx, acy), (tcx, tcy), (40, 140, 240), 2, cv2.LINE_AA)
                    mid_x = (acx + tcx) // 2
                    mid_y = (acy + tcy) // 2
                    cv2.putText(frame, "! TALKING", (mid_x - 25, mid_y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (40, 140, 240), 1, cv2.LINE_AA)

    return frame


def draw_objects(
    frame: np.ndarray,
    detected_objects: List[DetectedObject],
    seats: Dict[str, Any],
    unassigned_persons: Optional[List[Person]] = None,
) -> np.ndarray:
    """Renders detected objects, classification badges, and association vectors."""
    for obj in detected_objects:
        x1, y1, x2, y2 = map(int, obj.bbox)
        ocx = int((x1 + x2) / 2)
        ocy = int((y1 + y2) / 2)

        if obj.authorized:
            box_col = (94, 180, 80)  # Green for approved items
            tag_text = f"APP: {obj.class_name}"
        elif obj.class_name in ("cell phone", "remote"):
            box_col = (61, 69, 196)  # Critical red for phone
            tag_text = f"! PHONE {obj.conf:.2f}"
        elif obj.class_name == "book":
            box_col = (61, 69, 196)  # Critical red for chit
            tag_text = f"! CHIT {obj.conf:.2f}"
        else:
            box_col = (58, 135, 200)  # Amber for unregistered
            tag_text = f"UNREG: {obj.class_name}"

        # Draw object dashed/solid box
        cv2.rectangle(frame, (x1, y1), (x2, y2), box_col, 2 if not obj.stale else 1)

        # Draw tag
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.38
        (tw, th), _ = cv2.getTextSize(tag_text, font, font_scale, 1)
        tag_y1 = max(0, y1 - th - 4)
        tag_y2 = y1
        cv2.rectangle(frame, (x1, tag_y1), (x1 + tw + 6, tag_y2), box_col, -1)
        cv2.putText(frame, tag_text, (x1 + 3, y1 - 2), font, font_scale, (15, 27, 45), 1, cv2.LINE_AA)

        # Draw line connecting object to associated seat anchor or candidate
        if obj.associated_seat_id and obj.associated_seat_id in seats:
            seat_box = seats[obj.associated_seat_id].anchor_box
            scx = int((seat_box[0] + seat_box[2]) / 2)
            scy = int((seat_box[1] + seat_box[3]) / 2)
            cv2.line(frame, (ocx, ocy), (scx, scy), box_col, 1, cv2.LINE_AA)
        elif unassigned_persons:
            for p in unassigned_persons:
                if f"ID:{p.track_id}" in (obj.associated_seat_id or ""):
                    pcx, pcy = p.bbox_center()
                    cv2.line(frame, (ocx, ocy), (int(pcx), int(pcy)), box_col, 1, cv2.LINE_AA)

    return frame


def draw_person(
    frame: np.ndarray,
    person: Person,
    color: Optional[Tuple[int, int, int]] = None,
    label: Optional[str] = None,
    is_staff: bool = False,
    is_calibrating: bool = False,
    score: float = 0.0,
) -> np.ndarray:
    """Renders person bounding box, seat/score badge, and skeletal landmarks."""
    x1, y1, x2, y2 = map(int, person.bbox)

    if is_staff:
        box_color = (255, 140, 0)
        tag_bg = (200, 100, 0)
    elif is_calibrating:
        box_color = (58, 135, 200)
        tag_bg = box_color
    elif person.stale:
        box_color = (100, 100, 100) if color is None else color
        tag_bg = (80, 80, 80)
    else:
        box_color = get_status_color(score) if color is None else color
        tag_bg = box_color

    cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2 if not person.stale else 1)

    tag = label if label is not None else (f"ID:{person.track_id}" if person.track_id is not None else "Person")
    if not person.stale and not is_staff and not is_calibrating:
        tag += f" | {score:4.1f}"

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.42
    (tw, th), _ = cv2.getTextSize(tag, font, font_scale, 1)
    tag_y1 = max(0, y1 - th - 6)
    tag_y2 = y1
    tag_x2 = min(frame.shape[1], x1 + tw + 8)

    cv2.rectangle(frame, (x1, tag_y1), (tag_x2, tag_y2), tag_bg, -1)
    cv2.putText(frame, tag, (x1 + 4, y1 - 3), font, font_scale, (15, 27, 45), 1, cv2.LINE_AA)

    # Skeleton limbs
    min_conf = person.keypoint_min_conf
    for kp1, kp2 in SKELETON_PAIRS:
        if person.kp_visible(kp1, min_conf) and person.kp_visible(kp2, min_conf):
            x_a, y_a, c_a = person.kp(kp1)
            x_b, y_b, c_b = person.kp(kp2)
            pt_a = (int(round(x_a)), int(round(y_a)))
            pt_b = (int(round(x_b)), int(round(y_b)))
            limb_conf = (c_a + c_b) / 2.0
            limb_color = (255, 180, 50) if is_staff else box_color
            cv2.line(frame, pt_a, pt_b, limb_color, 2 if not person.stale else 1, cv2.LINE_AA)

    # Keypoints
    for kp_enum in KP:
        if person.kp_visible(kp_enum, min_conf=0.1):
            kx, ky, kc = person.kp(kp_enum)
            pt = (int(round(kx)), int(round(ky)))
            pt_color = (255, 200, 80) if is_staff else box_color
            radius = 3 if kc >= min_conf else 2
            cv2.circle(frame, pt, radius, pt_color, -1, cv2.LINE_AA)

HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17)
]


def draw_hands(
    frame: np.ndarray,
    seat_hands: Dict[str, Any],
) -> np.ndarray:
    """Renders MediaPipe 21 hand landmarks and grip/pinch badges."""
    h, w = frame.shape[:2]

    for sid, hands_list in seat_hands.items():
        for hand in hands_list:
            pts = hand.landmarks_2d
            pts_px = [(int(p[0] * w), int(p[1] * h)) for p in pts]

            color = (61, 69, 196) if hand.is_grip else (94, 180, 80)

            # Draw bones
            for p1_idx, p2_idx in HAND_CONNECTIONS:
                cv2.line(frame, pts_px[p1_idx], pts_px[p2_idx], color, 1, cv2.LINE_AA)

            # Draw joints
            for px, py in pts_px:
                cv2.circle(frame, (px, py), 2, color, -1, cv2.LINE_AA)

            # Draw grip gesture tag
            if hand.is_grip:
                wx, wy = pts_px[0]
                tag = "! PHONE GRIP"
                font = cv2.FONT_HERSHEY_SIMPLEX
                cv2.rectangle(frame, (wx - 4, wy - 18), (wx + 90, wy - 2), color, -1)
                cv2.putText(frame, tag, (wx, wy - 6), font, 0.32, (15, 27, 45), 1, cv2.LINE_AA)

    return frame


def render_scene(
    frame_image: np.ndarray,
    seat_assignments: Dict[str, Optional[Person]],
    staff_persons: List[Person],
    unassigned_persons: List[Person],
    detected_objects: List[DetectedObject],
    seat_map: Optional[SeatMap],
    calibrators: Optional[Dict[str, SeatCalibrator]],
    seat_features: Optional[Dict[str, SeatFeatures]],
    hud_info: Dict[str, Any],
    skeleton_only: bool = False,
    show_anchors: bool = True,
    show_features: bool = False,
    discovery_remaining_s: Optional[float] = None,
    seat_hands: Optional[Dict[str, Any]] = None,
) -> np.ndarray:
    """Renders all seat anchors, candidates, staff, detected objects, live features, and HUD."""
    if skeleton_only:
        h, w = frame_image.shape[:2]
        canvas = np.zeros((h, w, 3), dtype=np.uint8)
        for y in range(0, h, 60):
            cv2.line(canvas, (0, y), (w, y), (22, 38, 60), 1)
        for x in range(0, w, 60):
            cv2.line(canvas, (x, 0), (x, h), (22, 38, 60), 1)
    else:
        canvas = frame_image.copy()

    # Draw seat anchor boxes
    if show_anchors and seat_map and seat_map.seats:
        draw_seat_anchors(canvas, seat_map.seats, calibrators=calibrators)

    # Draw live feature bars
    if show_features and seat_features and seat_map and seat_map.seats:
        draw_features_overlay(canvas, seat_features, seat_map.seats)

    # Draw detected objects & association lines
    if detected_objects:
        seats_dict = seat_map.seats if seat_map else {}
        draw_objects(canvas, detected_objects, seats_dict, unassigned_persons=unassigned_persons)

    # Draw hand landmarks & grip gestures
    if seat_hands:
        draw_hands(canvas, seat_hands)

    # Draw seated candidates
    for sid, person in seat_assignments.items():
        if person is not None:
            seat_obj = seat_map.seats.get(sid) if seat_map else None
            score = seat_obj.score if seat_obj else 0.0
            cal = calibrators.get(sid) if calibrators else None
            is_cal = cal and cal.state == CalibrationState.CALIBRATING
            status_tag = " [CALIB]" if is_cal else ""
            label = f"SEAT: {sid}{status_tag}"
            draw_person(canvas, person, label=label, is_staff=False, is_calibrating=is_cal, score=score)

    # Draw unassigned candidates
    for p in unassigned_persons:
        label = f"Candidate (ID:{p.track_id})"
        draw_person(canvas, p, label=label, is_staff=False)

    # Draw STAFF in distinct color
    for p in staff_persons:
        label = f"STAFF (ID:{p.track_id})"
        draw_person(canvas, p, label=label, is_staff=True)

    draw_hud(canvas, hud_info)
    return canvas
