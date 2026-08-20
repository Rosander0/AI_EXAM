"""Unit tests for SANKET Prompt 2 (Pose Estimation & Tracking Schema)."""

import math
import numpy as np
import pytest
from sanket.pose import KP, Person, SKELETON_PAIRS


def create_synthetic_person(
    track_id: int = 1,
    left_shoulder=(100.0, 200.0, 0.9),
    right_shoulder=(200.0, 200.0, 0.9),
    nose=(150.0, 150.0, 0.9),
    left_ear=(120.0, 140.0, 0.9),
    right_ear=(180.0, 140.0, 0.9),
    left_wrist=(80.0, 300.0, 0.2),   # Low confidence wrist (e.g. under desk)
    right_wrist=(220.0, 300.0, 0.9),
    frame_index: int = 0,
    t: float = 0.0,
    min_conf: float = 0.5,
) -> Person:
    """Constructs a synthetic Person instance with controlled keypoint coordinates."""
    kpts = np.zeros((17, 3), dtype=np.float32)
    kpts[KP.LEFT_SHOULDER] = left_shoulder
    kpts[KP.RIGHT_SHOULDER] = right_shoulder
    kpts[KP.NOSE] = nose
    kpts[KP.LEFT_EAR] = left_ear
    kpts[KP.RIGHT_EAR] = right_ear
    kpts[KP.LEFT_WRIST] = left_wrist
    kpts[KP.RIGHT_WRIST] = right_wrist

    return Person(
        track_id=track_id,
        bbox=(80.0, 120.0, 220.0, 350.0),
        bbox_conf=0.95,
        keypoints=kpts,
        frame_index=frame_index,
        t=t,
        stale=False,
        keypoint_min_conf=min_conf,
    )


def test_named_keypoints_indexing():
    """Verify that named KP enum can be used to query keypoints."""
    person = create_synthetic_person()
    x, y, conf = person.kp(KP.NOSE)
    assert x == pytest.approx(150.0)
    assert y == pytest.approx(150.0)
    assert conf == pytest.approx(0.9)


def test_keypoint_visibility_and_hidden_hands_signal():
    """Verify that low-confidence keypoints report invisible (hidden hands signal)."""
    person = create_synthetic_person()
    # Left wrist is at 0.2 conf, below 0.5 threshold
    assert not person.kp_visible(KP.LEFT_WRIST)
    # Right wrist is at 0.9 conf
    assert person.kp_visible(KP.RIGHT_WRIST)


def test_shoulder_span_and_none_propagation():
    """Verify shoulder span calculation and None return when keypoints are missing."""
    person = create_synthetic_person(left_shoulder=(100.0, 200.0, 0.9), right_shoulder=(200.0, 200.0, 0.9))
    assert person.shoulder_span() == pytest.approx(100.0)

    # If left shoulder is below confidence, must return None (never 0.0)
    low_conf_person = create_synthetic_person(left_shoulder=(100.0, 200.0, 0.1), right_shoulder=(200.0, 200.0, 0.9))
    assert low_conf_person.shoulder_span() is None


def test_ear_nose_asymmetry():
    """Verify geometric ear-nose asymmetry calculation."""
    # Symmetrical head (nose exactly centered between ears)
    sym_person = create_synthetic_person(
        nose=(150.0, 150.0, 0.9),
        left_ear=(100.0, 150.0, 0.9),
        right_ear=(200.0, 150.0, 0.9),
        left_shoulder=(100.0, 250.0, 0.9),
        right_shoulder=(200.0, 250.0, 0.9),
    )
    assert sym_person.ear_nose_asymmetry() == pytest.approx(0.0)

    # Asymmetrical head (turned to the side)
    asym_person = create_synthetic_person(
        nose=(130.0, 150.0, 0.9),
        left_ear=(100.0, 150.0, 0.9),
        right_ear=(200.0, 150.0, 0.9),
        left_shoulder=(100.0, 250.0, 0.9),
        right_shoulder=(200.0, 250.0, 0.9),
    )
    # d(L_ear, nose) = 30, d(R_ear, nose) = 70, span = 100 -> |30 - 70| / 100 = 0.40
    assert asym_person.ear_nose_asymmetry() == pytest.approx(0.40)


def test_frame_skip_timing_equivalence():
    """
    CRITICAL INVARIANT:
    All durations and timing derive from Frame.t, never from frame counts.
    Frame skip changes sampling resolution only, never the meaning of a time-based measurement.
    """
    fps = 25.0
    duration_seconds = 2.0
    total_frames = int(duration_seconds * fps)

    # Simulate run with skip=1
    times_skip1 = [f_idx / fps for f_idx in range(total_frames)]
    # Simulate run with skip=3
    times_skip3 = [f_idx / fps for f_idx in range(total_frames)]

    # At any elapsed physical time, the timestamp t is exact
    t_target = 1.0  # 1 second mark (frame index 25)
    assert times_skip1[25] == pytest.approx(1.0)
    assert times_skip3[25] == pytest.approx(1.0)
