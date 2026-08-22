"""Pydantic request/response schemas matching DATA_CONTRACT.md exactly."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    ok: bool = True
    device: str
    model: str
    job_active: bool = False


class SessionCreateRequest(BaseModel):
    source: str
    config_overrides: Optional[Dict[str, Any]] = None


class EventSchema(BaseModel):
    event_id: str
    session_id: str
    seat_id: str
    track_id: Optional[int] = None
    t_start: float
    t_end: float
    frame_start: int
    frame_end: int
    rule: str
    points: float
    score_after: float
    confidence: float
    severity: str
    reason: str
    clip_path: Optional[str] = None
    thumb_path: Optional[str] = None


class SeatStateSchema(BaseModel):
    seat_id: str
    grid_row: int
    grid_col: int
    score: float
    peak_score: float
    event_count: int
    distinct_rules: int
    sustained_seconds: float
    status: str
    calibrated: bool
    last_reason: Optional[str] = None
    occupied: bool


class SessionSchema(BaseModel):
    session_id: str
    source: str
    state: str  # "queued" | "running" | "done" | "failed"
    progress: float
    frames_processed: int
    frames_total: Optional[int] = None
    duration_s: float
    fps_processing: float
    seats_tracked: int
    events_total: int
    alerts_total: int
    config_hash: Optional[str] = None
    started_at: str
    ended_at: Optional[str] = None
    error_message: Optional[str] = None


class StaffStateSchema(BaseModel):
    staff_id: str
    track_id: int
    score: float
    peak_score: float
    event_count: int
    status: str
    median_dwell_s: float
    total_visits: int
    total_dwell_s: float
    last_reason: Optional[str] = None


class StaffEventSchema(BaseModel):
    event_id: str
    session_id: str
    staff_id: str
    seat_id: Optional[str] = None
    track_id: Optional[int] = None
    t_start: float
    t_end: float
    frame_start: int
    frame_end: int
    rule: str
    points: float
    score_after: float
    confidence: float
    severity: str
    reason: str

