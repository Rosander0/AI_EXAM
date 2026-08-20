"""Unit tests for SANKET Prompt 3 (Seat Anchoring & Staff Classification)."""

import numpy as np
import pytest
from sanket.config import load_config
from sanket.pose import KP, Person
from sanket.seats import Seat, SeatMap, compute_iou


def create_person(track_id: int, bbox: tuple, t: float = 0.0, frame_index: int = 0) -> Person:
    """Helper to create a Person with a given bbox and track ID."""
    kpts = np.zeros((17, 3), dtype=np.float32)
    kpts[:, 2] = 0.9  # Visible landmarks
    return Person(
        track_id=track_id,
        bbox=bbox,
        bbox_conf=0.9,
        keypoints=kpts,
        frame_index=frame_index,
        t=t,
        stale=False,
    )


def test_compute_iou():
    """Verify IoU calculation on identical, overlapping, and disjoint boxes."""
    b1 = (10.0, 10.0, 50.0, 50.0)
    # Identical
    assert compute_iou(b1, b1) == pytest.approx(1.0)
    # Half-overlap (area 1600 each, inter 800, union 2400)
    b2 = (10.0, 10.0, 50.0, 30.0)
    assert compute_iou(b1, b2) == pytest.approx(800.0 / 1600.0)
    # Disjoint
    b3 = (100.0, 100.0, 150.0, 150.0)
    assert compute_iou(b1, b3) == pytest.approx(0.0)


def test_seat_map_auto_discovery_and_grid_ordering():
    """Verify spatial clustering and reading-order grid assignment (S01, S02...)."""
    cfg = load_config("config.yaml")
    cfg.identity["discovery_seconds"] = 1.0  # Fast discovery for test
    seat_map = SeatMap(cfg)

    # 4 students seated in a 2x2 grid
    # Row 1: (100, 100) and (400, 100)
    # Row 2: (100, 400) and (400, 400)
    p1 = create_person(1, (100.0, 100.0, 200.0, 250.0))
    p2 = create_person(2, (400.0, 100.0, 500.0, 250.0))
    p3 = create_person(3, (100.0, 400.0, 200.0, 550.0))
    p4 = create_person(4, (400.0, 400.0, 500.0, 550.0))

    # Feed frames to complete discovery
    for frame_i in range(10):
        t = frame_i * 0.1
        seat_map.update([p1, p2, p3, p4], t, (720, 1280))

    # Force auto discovery
    seat_map._run_auto_discovery()
    assert seat_map.is_discovered
    assert len(seat_map.seats) == 4

    # Check reading order: S01 top-left, S02 top-right, S03 bottom-left, S04 bottom-right
    s01 = seat_map.seats["S01"]
    assert s01.grid_row == 1 and s01.grid_col == 1
    s02 = seat_map.seats["S02"]
    assert s02.grid_row == 1 and s02.grid_col == 2
    s03 = seat_map.seats["S03"]
    assert s03.grid_row == 2 and s03.grid_col == 1
    s04 = seat_map.seats["S04"]
    assert s04.grid_row == 2 and s04.grid_col == 2


def test_id_stability_across_tracker_flips():
    """Verify that if tracker assigns a new ID to the same seat, seat anchor maintains student identity."""
    cfg = load_config("config.yaml")
    seat_map = SeatMap(cfg)
    seat_map.seats["S01"] = Seat(
        seat_id="S01",
        grid_row=1,
        grid_col=1,
        anchor_box=(100.0, 100.0, 200.0, 250.0),
    )
    seat_map.is_discovered = True

    # Frame 1: Candidate with track_id = 1 occupies S01
    p_orig = create_person(1, (100.0, 100.0, 200.0, 250.0), t=0.0)
    assignments, staff = seat_map.update([p_orig], t=0.0, frame_shape=(720, 1280))
    assert assignments["S01"] is not None
    assert seat_map.seats["S01"].current_track_id == 1

    # Frame 10: Tracker flips ID from 1 to 99 for the same position
    p_flipped = create_person(99, (102.0, 101.0, 201.0, 252.0), t=1.0)
    assignments, staff = seat_map.update([p_flipped], t=1.0, frame_shape=(720, 1280))

    assert assignments["S01"] is not None
    assert seat_map.seats["S01"].current_track_id == 99
    # S01 retains both track IDs in history
    assert seat_map.seats["S01"].binding_history == [1, 99]


def test_staff_classification():
    """Verify that walking persons (unanchored or multi-seat) are classified as STAFF."""
    cfg = load_config("config.yaml")
    cfg.identity["staff_grace_seconds"] = 5.0
    seat_map = SeatMap(cfg)
    seat_map.seats["S01"] = Seat(
        seat_id="S01",
        grid_row=1,
        grid_col=1,
        anchor_box=(100.0, 100.0, 200.0, 250.0),
    )
    seat_map.is_discovered = True

    # Candidate at S01
    candidate = create_person(1, (100.0, 100.0, 200.0, 250.0), t=0.0)
    # Walking invigilator in the hallway
    invigilator = create_person(999, (800.0, 500.0, 900.0, 700.0), t=0.0)

    # Initial frame
    _, staff = seat_map.update([candidate, invigilator], t=0.0, frame_shape=(720, 1280))
    assert len(staff) == 0

    # Advance time beyond staff_grace_seconds (e.g. t = 6.0s)
    invigilator_later = create_person(999, (750.0, 480.0, 850.0, 680.0), t=6.0)
    assignments, staff = seat_map.update([candidate, invigilator_later], t=6.0, frame_shape=(720, 1280))

    # Invigilator classified as STAFF and excluded from candidate assignments
    assert len(staff) == 1
    assert staff[0].track_id == 999
    assert assignments["S01"].track_id == 1
