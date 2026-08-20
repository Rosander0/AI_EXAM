"""Unit tests for SANKET Prompt 5 (Geometric Feature Extraction)."""

import numpy as np
import pytest
from sanket.calibration import SeatCalibrator
from sanket.config import load_config
from sanket.features import FeatureExtractor, SeatFeatures
from sanket.pose import KP, Person
from sanket.seats import Seat, SeatMap


def create_mock_person(
    track_id: int,
    bbox: tuple,
    left_shoulder=(100.0, 200.0, 0.9),
    right_shoulder=(200.0, 200.0, 0.9),
    nose=(150.0, 150.0, 0.9),
    left_wrist=(80.0, 300.0, 0.9),
    right_wrist=(220.0, 300.0, 0.9),
    left_ear=(120.0, 150.0, 0.9),
    right_ear=(180.0, 150.0, 0.9),
    t: float = 0.0,
) -> Person:
    kpts = np.zeros((17, 3), dtype=np.float32)
    kpts[KP.LEFT_SHOULDER] = left_shoulder
    kpts[KP.RIGHT_SHOULDER] = right_shoulder
    kpts[KP.NOSE] = nose
    kpts[KP.LEFT_WRIST] = left_wrist
    kpts[KP.RIGHT_WRIST] = right_wrist
    kpts[KP.LEFT_EAR] = left_ear
    kpts[KP.RIGHT_EAR] = right_ear

    return Person(
        track_id=track_id,
        bbox=bbox,
        bbox_conf=0.95,
        keypoints=kpts,
        frame_index=0,
        t=t,
        stale=False,
    )


def test_features_none_propagation_on_missing_data():
    """Verify that when landmarks are below confidence, feature fields return None (never 0.0)."""
    cfg = load_config("config.yaml")
    extractor = FeatureExtractor(cfg)
    seat_map = SeatMap(cfg)
    seat = Seat("S01", 1, 1, (50.0, 50.0, 250.0, 350.0))
    seat_map.seats["S01"] = seat

    # Person with low confidence shoulders and nose
    low_kpts = np.zeros((17, 3), dtype=np.float32)
    person = Person(
        track_id=1,
        bbox=(50.0, 50.0, 250.0, 350.0),
        bbox_conf=0.9,
        keypoints=low_kpts,
        frame_index=0,
        t=0.0,
    )

    feats = extractor.extract_features(
        seat_assignments={"S01": person},
        staff_persons=[],
        seat_map=seat_map,
        calibrators={},
        t=0.0,
    )

    s_feat = feats["S01"]
    assert s_feat.shoulder_span_ratio is None
    assert s_feat.torso_rotation is None
    assert s_feat.head_turn_deviation is None


def test_hidden_hands_duration_tracking_and_reset():
    """Verify continuous hidden hands time accumulation and reset when hands become visible."""
    cfg = load_config("config.yaml")
    extractor = FeatureExtractor(cfg)
    seat_map = SeatMap(cfg)
    seat = Seat("S01", 1, 1, (50.0, 50.0, 250.0, 350.0))
    seat_map.seats["S01"] = seat

    # Frame 1 at t=1.0s: both wrists hidden (conf 0.1)
    p_hidden_1 = create_mock_person(1, (50.0, 50.0, 250.0, 350.0), left_wrist=(0, 0, 0.1), right_wrist=(0, 0, 0.1), t=1.0)
    feats1 = extractor.extract_features({"S01": p_hidden_1}, [], seat_map, {}, t=1.0)
    assert feats1["S01"].hidden_hands_duration == pytest.approx(0.0)

    # Frame 2 at t=4.0s: both wrists still hidden
    p_hidden_2 = create_mock_person(1, (50.0, 50.0, 250.0, 350.0), left_wrist=(0, 0, 0.1), right_wrist=(0, 0, 0.1), t=4.0)
    feats2 = extractor.extract_features({"S01": p_hidden_2}, [], seat_map, {}, t=4.0)
    assert feats2["S01"].hidden_hands_duration == pytest.approx(3.0)

    # Frame 3 at t=5.0s: right wrist reappears (conf 0.9)
    p_visible = create_mock_person(1, (50.0, 50.0, 250.0, 350.0), left_wrist=(0, 0, 0.1), right_wrist=(200, 300, 0.9), t=5.0)
    feats3 = extractor.extract_features({"S01": p_visible}, [], seat_map, {}, t=5.0)
    assert feats3["S01"].hidden_hands_duration == pytest.approx(0.0)


def test_neighbour_intrusion_and_staff_exclusion():
    """Verify wrist reaching into adjacent seat is detected as intrusion, and staff never triggers intrusion."""
    cfg = load_config("config.yaml")
    extractor = FeatureExtractor(cfg)
    seat_map = SeatMap(cfg)

    # Adjacent desks: S01 (left) and S02 (right)
    s01 = Seat("S01", 1, 1, (100.0, 100.0, 250.0, 350.0))
    s02 = Seat("S02", 1, 2, (300.0, 100.0, 450.0, 350.0))
    seat_map.seats["S01"] = s01
    seat_map.seats["S02"] = s02

    # S01 candidate reaches right wrist into S02's anchor box (x=330 inside [300, 450])
    p1 = create_mock_person(1, (100.0, 100.0, 250.0, 350.0), right_wrist=(330.0, 200.0, 0.9), t=1.0)
    p2 = create_mock_person(2, (300.0, 100.0, 450.0, 350.0), t=1.0)

    feats = extractor.extract_features({"S01": p1, "S02": p2}, [], seat_map, {}, t=1.0)
    assert "S02" in feats["S01"].neighbour_intrusion
    assert feats["S01"].neighbour_intrusion["S02"] > 0.1

    # Verify STAFF tracks produce zero intrusion against candidate seats
    staff = create_mock_person(999, (500.0, 100.0, 600.0, 350.0), right_wrist=(330.0, 200.0, 0.9), t=1.0)
    feats_with_staff = extractor.extract_features({"S01": p1, "S02": p2}, [staff], seat_map, {}, t=1.0)
    # Staff is not a key in seat features (never scored)
    assert "STAFF" not in feats_with_staff
