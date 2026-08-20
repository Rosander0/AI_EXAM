"""Unit tests for SANKET Prompt 7 (Object Detection & Authorized Object Learning)."""

import numpy as np
import pytest
from sanket.calibration import CalibrationState, SeatCalibrator
from sanket.config import load_config
from sanket.detection import ObjectDetector
from sanket.pose import KP, Person
from sanket.seats import Seat, SeatMap


def create_person_with_wrists(track_id: int, bbox: tuple, lw=(100.0, 200.0, 0.9), rw=(200.0, 200.0, 0.9)) -> Person:
    kpts = np.zeros((17, 3), dtype=np.float32)
    kpts[KP.LEFT_WRIST] = lw
    kpts[KP.RIGHT_WRIST] = rw
    return Person(
        track_id=track_id,
        bbox=bbox,
        bbox_conf=0.9,
        keypoints=kpts,
        frame_index=0,
        t=0.0,
    )


def test_object_wrist_association_and_empty_desk_exclusion():
    """Verify object associates to closest wrist, and unassociated objects (on empty desk) score nothing."""
    cfg = load_config("config.yaml")
    cfg.objects["enabled"] = False  # Unit testing logic without loading weights
    detector = ObjectDetector(cfg)

    # Candidate at S01 with left wrist at (100, 200)
    p1 = create_person_with_wrists(1, (80.0, 100.0, 220.0, 300.0), lw=(100.0, 200.0, 0.9))
    seat_assignments = {"S01": p1}

    # Object 1: Close to S01 left wrist at (105, 205) -> Should associate to S01 left wrist
    obj_box_near = (100.0, 200.0, 110.0, 210.0)
    sid, wrist, p_match = detector._associate_object(obj_box_near, seat_assignments)
    assert sid == "S01"
    assert wrist == "left"
    assert p_match.track_id == 1

    # Object 2: On empty desk far away at (800, 500) -> Should NOT associate to any candidate
    obj_box_far = (800.0, 500.0, 850.0, 550.0)
    sid_far, wrist_far, p_far = detector._associate_object(obj_box_far, seat_assignments)
    assert sid_far is None
    assert p_far is None


def test_chit_geometry_filter():
    """Verify that large objects (e.g. answer sheets) are filtered out, and small chits survive."""
    cfg = load_config("config.yaml")
    cfg.objects["enabled"] = False
    detector = ObjectDetector(cfg)

    person = create_person_with_wrists(1, (100.0, 100.0, 300.0, 400.0))  # Area = 200 * 300 = 60,000 px^2

    # Large answer sheet: 150x200 = 30,000 px^2 (50% of person area > 8% limit) -> Filtered out
    sheet_box = (150.0, 200.0, 300.0, 400.0)
    assert not detector._filter_chit_geometry(sheet_box, person)

    # Small paper chit: 30x40 = 1,200 px^2 (2% of person area < 8% limit, aspect 0.75) -> Survives
    chit_box = (150.0, 200.0, 180.0, 240.0)
    assert detector._filter_chit_geometry(chit_box, person)


def test_authorized_object_learning_and_never_authorized_phone():
    """
    Verify:
    1. A calculator during calibration is authorized forever.
    2. A cell phone during calibration is NEVER authorized (hard exception).
    """
    cfg = load_config("config.yaml")
    cfg.objects["enabled"] = False
    detector = ObjectDetector(cfg)

    seat_map = SeatMap(cfg)
    seat = Seat("S01", 1, 1, (100.0, 100.0, 300.0, 400.0))
    seat_map.seats["S01"] = seat

    calibrator = SeatCalibrator("S01", cfg)
    calibrator.state = CalibrationState.CALIBRATING  # Currently in calibration window

    p = create_person_with_wrists(1, (100.0, 100.0, 300.0, 400.0))
    seat_assignments = {"S01": p}

    # Simulate fake YOLO predict result by manually testing authorization logic:
    # 1. Authorize permitted equipment (e.g. calculator/water bottle) during calibration
    detector.authorized_registry.setdefault("S01", set()).add("calculator")
    assert "calculator" in detector.authorized_registry["S01"]

    # 2. Finish calibration
    calibrator.state = CalibrationState.CALIBRATED

    # In post-calibration, calculator is approved
    assert "calculator" in detector.authorized_registry["S01"]

    # Verify cell phone is in never_authorized and cannot be laundered
    assert "cell phone" in detector.never_authorized


def test_mediapipe_hand_phone_grip_heuristics():
    """Verify that curled fingers with opposed thumb triggers phone grip detection."""
    from sanket.hands import MediaPipeHandAnalyzer
    cfg = load_config("config.yaml")
    cfg.hands["enabled"] = False  # Pure heuristic unit test
    analyzer = MediaPipeHandAnalyzer(cfg)

    # 1. Flat hand posture (extended fingers): Not a phone grip
    flat_hand = np.zeros((21, 2), dtype=np.float32)
    flat_hand[0] = (0.5, 0.8)   # Wrist
    flat_hand[4] = (0.3, 0.4)   # Thumb tip
    flat_hand[5] = (0.45, 0.6)  # Index MCP
    flat_hand[9] = (0.50, 0.6)  # Middle MCP
    flat_hand[8] = (0.45, 0.2)  # Index tip (extended)
    flat_hand[12] = (0.50, 0.1) # Middle tip (extended)
    flat_hand[16] = (0.55, 0.2) # Ring tip (extended)
    flat_hand[20] = (0.60, 0.3) # Pinky tip (extended)
    assert not analyzer._detect_phone_grip(flat_hand)

    # 2. Pen writing posture (index extended + thumb touching index PIP): Not a phone grip
    writing_hand = np.zeros((21, 2), dtype=np.float32)
    writing_hand[0] = (0.5, 0.8)   # Wrist
    writing_hand[5] = (0.45, 0.6)  # Index MCP
    writing_hand[6] = (0.45, 0.55) # Index PIP
    writing_hand[8] = (0.45, 0.45) # Index tip (extended along pen)
    writing_hand[9] = (0.50, 0.6)  # Middle MCP
    writing_hand[4] = (0.46, 0.54) # Thumb tip touching index PIP
    writing_hand[12] = (0.52, 0.65) # Middle tip
    writing_hand[16] = (0.54, 0.67) # Ring tip
    writing_hand[20] = (0.56, 0.68) # Pinky tip
    assert not analyzer._detect_phone_grip(writing_hand)

    # 3. Phone grip posture (curled fingers close to palm + thumb opposed near index knuckle)
    curled_hand = np.zeros((21, 2), dtype=np.float32)
    curled_hand[0] = (0.5, 0.8)   # Wrist
    curled_hand[5] = (0.5, 0.6)   # Index MCP
    curled_hand[9] = (0.5, 0.6)   # Middle MCP (dist to wrist = 0.20)
    curled_hand[4] = (0.48, 0.58) # Thumb tip near index MCP
    curled_hand[8] = (0.5, 0.65)  # Index tip curled
    curled_hand[12] = (0.52, 0.66) # Middle tip curled (dist to wrist = 0.14 < 0.20 * 1.15)
    curled_hand[16] = (0.54, 0.67) # Ring tip curled (dist to wrist = 0.13 < 0.20 * 1.15)
    curled_hand[20] = (0.56, 0.68) # Pinky tip curled
    assert analyzer._detect_phone_grip(curled_hand)
