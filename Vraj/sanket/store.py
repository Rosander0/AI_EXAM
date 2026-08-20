"""SQLite database persistence for SANKET.

Matches DATA_CONTRACT.md schema exactly.
Uses stdlib sqlite3 in WAL mode for concurrent, non-blocking reads during analysis.
"""

from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional, Set, Tuple

from sanket.scoring import Event
from sanket.seats import Seat


class SessionStore:
    """Encapsulates SQLite operations for storing sessions, events, seats, and metrics."""

    def __init__(self, db_path: str | Path = "data/sanket.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self) -> None:
        """Initializes database tables matching DATA_CONTRACT.md schema."""
        with self._get_connection() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                state TEXT NOT NULL,
                progress REAL DEFAULT 0.0,
                frames_processed INTEGER DEFAULT 0,
                frames_total INTEGER,
                duration_s REAL DEFAULT 0.0,
                fps_processing REAL DEFAULT 0.0,
                seats_tracked INTEGER DEFAULT 0,
                events_total INTEGER DEFAULT 0,
                alerts_total INTEGER DEFAULT 0,
                config_hash TEXT,
                started_at TEXT,
                ended_at TEXT,
                error_message TEXT
            );

            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                seat_id TEXT NOT NULL,
                track_id INTEGER,
                t_start REAL NOT NULL,
                t_end REAL NOT NULL,
                frame_start INTEGER NOT NULL,
                frame_end INTEGER NOT NULL,
                rule TEXT NOT NULL,
                points REAL NOT NULL,
                score_after REAL NOT NULL,
                confidence REAL NOT NULL,
                severity TEXT NOT NULL,
                reason TEXT NOT NULL,
                clip_path TEXT,
                thumb_path TEXT,
                PRIMARY KEY (session_id, event_id),
                FOREIGN KEY (session_id) REFERENCES sessions (session_id)
            );

            CREATE TABLE IF NOT EXISTS seat_states (
                session_id TEXT NOT NULL,
                seat_id TEXT NOT NULL,
                grid_row INTEGER NOT NULL,
                grid_col INTEGER NOT NULL,
                score REAL DEFAULT 0.0,
                peak_score REAL DEFAULT 0.0,
                event_count INTEGER DEFAULT 0,
                distinct_rules INTEGER DEFAULT 0,
                sustained_seconds REAL DEFAULT 0.0,
                status TEXT DEFAULT 'calm',
                calibrated INTEGER DEFAULT 0,
                last_reason TEXT,
                occupied INTEGER DEFAULT 0,
                PRIMARY KEY (session_id, seat_id),
                FOREIGN KEY (session_id) REFERENCES sessions (session_id)
            );

            CREATE TABLE IF NOT EXISTS seat_timeline (
                session_id TEXT NOT NULL,
                seat_id TEXT NOT NULL,
                t REAL NOT NULL,
                score REAL NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions (session_id)
            );

            CREATE TABLE IF NOT EXISTS object_registry (
                session_id TEXT NOT NULL,
                seat_id TEXT NOT NULL,
                object_class TEXT NOT NULL,
                first_seen_t REAL NOT NULL,
                authorized INTEGER NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions (session_id)
            );

            CREATE TABLE IF NOT EXISTS stream_gaps (
                session_id TEXT NOT NULL,
                t_start REAL NOT NULL,
                t_end REAL NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions (session_id)
            );

            CREATE INDEX IF NOT EXISTS idx_events_session_id ON events (session_id, event_id);
            CREATE INDEX IF NOT EXISTS idx_seat_timeline_sess ON seat_timeline (session_id, seat_id, t);
            """)

    def create_session(self, session_data: Dict[str, Any]) -> None:
        """Inserts a new session record."""
        with self._get_connection() as conn:
            conn.execute("""
            INSERT OR REPLACE INTO sessions (
                session_id, source, state, progress, frames_processed, frames_total,
                duration_s, fps_processing, seats_tracked, events_total, alerts_total,
                config_hash, started_at, ended_at, error_message
            ) VALUES (
                :session_id, :source, :state, :progress, :frames_processed, :frames_total,
                :duration_s, :fps_processing, :seats_tracked, :events_total, :alerts_total,
                :config_hash, :started_at, :ended_at, :error_message
            )
            """, session_data)

    def update_session(self, session_id: str, updates: Dict[str, Any]) -> None:
        """Updates fields of an existing session record."""
        keys = list(updates.keys())
        set_clause = ", ".join([f"{k} = :{k}" for k in keys])
        params = dict(updates)
        params["session_id"] = session_id

        with self._get_connection() as conn:
            conn.execute(f"UPDATE sessions SET {set_clause} WHERE session_id = :session_id", params)

    def insert_events(self, events: List[Event]) -> None:
        """Batch inserts new Event records."""
        if not events:
            return
        with self._get_connection() as conn:
            conn.executemany("""
            INSERT OR REPLACE INTO events (
                event_id, session_id, seat_id, track_id, t_start, t_end,
                frame_start, frame_end, rule, points, score_after, confidence,
                severity, reason, clip_path, thumb_path
            ) VALUES (
                :event_id, :session_id, :seat_id, :track_id, :t_start, :t_end,
                :frame_start, :frame_end, :rule, :points, :score_after, :confidence,
                :severity, :reason, :clip_path, :thumb_path
            )
            """, [e.to_dict() for e in events])

    def save_seat_states(self, session_id: str, seats: Dict[str, Seat]) -> None:
        """Saves current state for all seats."""
        with self._get_connection() as conn:
            for sid, seat in seats.items():
                conn.execute("""
                INSERT OR REPLACE INTO seat_states (
                    session_id, seat_id, grid_row, grid_col, score, peak_score,
                    event_count, distinct_rules, sustained_seconds, status,
                    calibrated, last_reason, occupied
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """, (
                    session_id, sid, seat.grid_row, seat.grid_col,
                    round(seat.score, 1), round(seat.peak_score, 1),
                    seat.event_count, seat.distinct_rules,
                    round(seat.sustained_seconds, 1),
                    getattr(seat, "status", "calm"),
                    1 if getattr(seat, "calibrated", False) else 0,
                    seat.last_reason,
                    1 if seat.occupied else 0,
                ))

    def record_timeline_sample(self, session_id: str, sid: str, t: float, score: float) -> None:
        """Records a periodic score sample for timeline charting."""
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO seat_timeline (session_id, seat_id, t, score) VALUES (?, ?, ?, ?)",
                (session_id, sid, round(t, 2), round(score, 1)),
            )

    def record_object_registry(self, session_id: str, sid: str, obj_class: str, t: float, authorized: bool) -> None:
        """Records an entry in the authorized object registry."""
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO object_registry (session_id, seat_id, object_class, first_seen_t, authorized) VALUES (?, ?, ?, ?, ?)",
                (session_id, sid, obj_class, round(t, 2), 1 if authorized else 0),
            )

    def record_stream_gap(self, session_id: str, t_start: float, t_end: float) -> None:
        """Records an unmonitored stream gap interval."""
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO stream_gaps (session_id, t_start, t_end) VALUES (?, ?, ?)",
                (session_id, round(t_start, 2), round(t_end, 2)),
            )

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
            return dict(row) if row else None

    def get_events(self, session_id: str, since_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            if since_id:
                rows = conn.execute(
                    "SELECT * FROM events WHERE session_id = ? AND event_id > ? ORDER BY event_id ASC",
                    (session_id, since_id),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM events WHERE session_id = ? ORDER BY event_id ASC",
                    (session_id,),
                ).fetchall()
            return [dict(r) for r in rows]

    def get_seat_states(self, session_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM seat_states WHERE session_id = ? ORDER BY grid_row, grid_col",
                (session_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_object_registry(self, session_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM object_registry WHERE session_id = ?", (session_id,)).fetchall()
            return [dict(r) for r in rows]

    def get_stream_gaps(self, session_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM stream_gaps WHERE session_id = ?", (session_id,)).fetchall()
            return [dict(r) for r in rows]
