"""Unit tests for SANKET Prompt 11 (Evidence Clips & Eval Harness)."""

import json
from pathlib import Path
import numpy as np
import pytest
from sanket.clips import ClipExtractor
from sanket.scoring import Event
from sanket.store import SessionStore
from tools.eval import evaluate_session, temporal_iou


def test_temporal_iou_calculation():
    """Verify 1D temporal IoU overlap logic."""
    # Identical intervals -> IoU = 1.0
    assert temporal_iou(1.0, 5.0, 1.0, 5.0) == pytest.approx(1.0)

    # Disjoint intervals -> IoU = 0.0
    assert temporal_iou(1.0, 2.0, 3.0, 4.0) == pytest.approx(0.0)

    # 50% overlap: [0, 4] and [2, 6] -> intersection [2,4] = 2, union [0,6] = 6 -> IoU = 2/6 = 0.333
    assert temporal_iou(0.0, 4.0, 2.0, 6.0) == pytest.approx(2.0 / 6.0)


def test_eval_harness_precision_recall_fa_per_hour(tmp_path: Path):
    """Verify evaluation metrics computation against ground-truth JSON."""
    db_file = tmp_path / "eval_sanket.db"
    store = SessionStore(db_path=db_file)
    session_id = "sess_eval_test"

    store.create_session({
        "session_id": session_id,
        "source": "exam.mp4",
        "state": "done",
        "progress": 1.0,
        "frames_processed": 1000,
        "frames_total": 1000,
        "duration_s": 3600.0,  # Exactly 1.0 hour
        "fps_processing": 25.0,
        "seats_tracked": 2,
        "events_total": 2,
        "alerts_total": 1,
        "config_hash": "a1b2c3",
        "started_at": "2026-08-22T10:00:00",
        "ended_at": None,
        "error_message": None,
    })

    # Event 1: Matches GT interval [10, 14] -> True Positive
    # Event 2: At [100, 102] with no GT match -> False Positive
    e1 = Event("evt_01", session_id, "S01", 1, 10.0, 14.0, 250, 350, "head_turn", 10.0, 10.0, 0.9, "warning", "Head turned")
    e2 = Event("evt_02", session_id, "S01", 1, 100.0, 102.0, 2500, 2550, "head_turn", 10.0, 20.0, 0.9, "warning", "Head turned")
    store.insert_events([e1, e2])

    # Ground truth JSON: 1 event at [10, 14]
    gt_file = tmp_path / "gt.json"
    gt_file.write_text(json.dumps([
        {"t_start": 10.0, "t_end": 14.0, "seat_id": "S01", "rule": "head_turn", "description": "Actual head turn"}
    ]), encoding="utf-8")

    metrics = evaluate_session(session_id, gt_file, store=store, output_dir=tmp_path)

    assert metrics["true_positives"] == 1
    assert metrics["false_positives"] == 1
    assert metrics["false_negatives"] == 0
    assert metrics["precision"] == pytest.approx(0.5)
    assert metrics["recall"] == pytest.approx(1.0)
    assert metrics["false_alarms_per_hour"] == pytest.approx(1.0)


def test_async_clip_extractor(tmp_path: Path):
    """Verify ClipExtractor asynchronously writes .mp4 and _thumb.jpg without crashing."""
    clips_dir = tmp_path / "clips"
    extractor = ClipExtractor(store=None, clips_dir=clips_dir)

    evt = Event("evt_test_clip", "sess_01", "S01", 1, 1.0, 2.0, 25, 50, "object_phone", 100.0, 100.0, 0.9, "critical", "Phone")

    # Ring buffer with 10 dummy frames
    dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
    ring_buffer = [(float(i) * 0.1, dummy_img) for i in range(10)]

    extractor.enqueue_clip(evt, ring_buffer, fps=10.0)
    extractor.close()

    assert (clips_dir / "evt_test_clip_thumb.jpg").is_file()
