"""Unit tests for SANKET Prompt 8 (Session Store & Reports)."""

from pathlib import Path
import pytest
from sanket.report import generate_reports, verify_consistency
from sanket.scoring import Event
from sanket.seats import Seat
from sanket.store import SessionStore


def test_session_store_crud_and_consistency(tmp_path: Path):
    """Verify SQLite CRUD, report generation, and consistency verification."""
    db_file = tmp_path / "test_sanket.db"
    store = SessionStore(db_path=db_file)
    session_id = "sess_unit_test_01"

    # Create session
    store.create_session({
        "session_id": session_id,
        "source": "mock_exam.mp4",
        "state": "running",
        "progress": 0.0,
        "frames_processed": 100,
        "frames_total": 100,
        "duration_s": 4.0,
        "fps_processing": 25.0,
        "seats_tracked": 2,
        "events_total": 2,
        "alerts_total": 1,
        "config_hash": "a1b2c3",
        "started_at": "2026-08-22T10:00:00",
        "ended_at": None,
        "error_message": None,
    })

    # Insert events (one warning, one critical)
    e1 = Event(
        event_id="evt_0001",
        session_id=session_id,
        seat_id="S01",
        track_id=1,
        t_start=1.0,
        t_end=2.0,
        frame_start=25,
        frame_end=50,
        rule="head_turn",
        points=10.0,
        score_after=10.0,
        confidence=0.8,
        severity="warning",
        reason="Head turned left, 2.8 deviations",
    )
    e2 = Event(
        event_id="evt_0002",
        session_id=session_id,
        seat_id="S01",
        track_id=1,
        t_start=2.5,
        t_end=3.5,
        frame_start=60,
        frame_end=85,
        rule="object_phone",
        points=100.0,
        score_after=110.0,
        confidence=0.95,
        severity="critical",
        reason="Prohibited mobile phone detected near right wrist",
    )
    store.insert_events([e1, e2])

    # Save seat states
    s01 = Seat("S01", 1, 1, (10, 10, 50, 50), score=110.0, sustained_seconds=1.5)
    s01.status = "alert"
    s02 = Seat("S02", 1, 2, (60, 10, 100, 50), score=0.0, sustained_seconds=0.0)
    store.save_seat_states(session_id, {"S01": s01, "S02": s02})

    # Generate reports
    html_path, csv_path = generate_reports(session_id, store, output_dir=tmp_path)
    assert html_path.is_file()
    assert csv_path.is_file()

    # Run consistency verification
    assert verify_consistency(session_id, store, html_path, csv_path)

    # Invariant Check: The word "cheating" must NEVER appear anywhere in the reports
    html_text = html_path.read_text(encoding="utf-8").lower()
    csv_text = csv_path.read_text(encoding="utf-8").lower()
    assert "cheating" not in html_text
    assert "cheating" not in csv_text
