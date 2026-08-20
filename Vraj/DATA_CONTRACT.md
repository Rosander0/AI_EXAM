# SANKET Data Contract

**Status: Frozen at Hour Zero**
Backend and frontend build against this specification in parallel.

---

## 1. Schemas

### Event
Represents an individual behavioral detection or threshold event.
```json
{
  "event_id": "evt_0007",
  "session_id": "sess_20260822_1030",
  "seat_id": "S12",
  "track_id": 4,
  "t_start": 412.5,
  "t_end": 418.2,
  "frame_start": 12375,
  "frame_end": 12546,
  "rule": "head_turn",
  "points": 10,
  "score_after": 104.0,
  "confidence": 0.78,
  "severity": "critical",
  "reason": "Head turned 34 degrees off own baseline, held 1.4 s",
  "clip_path": "clips/evt_0007.mp4",
  "thumb_path": "thumbs/evt_0007.jpg"
}
```
- `rule` $\in$ `["head_turn", "neighbour_reach", "hidden_hands", "turning_back", "repeated_action", "object_phone", "object_chit", "object_unregistered", "hand_phone_grip", "hand_chit_pinch"]`
- `severity` $\in$ `["critical", "warning", "info"]`
  - `critical`: Threshold crossed ($\ge 100$), or instant-alert object.
  - `warning`: Rule fired, below threshold.
  - `info`: Calibration or system notification.

### Seat State
Represents the real-time operational status of an anchored seat.
```json
{
  "seat_id": "S12",
  "grid_row": 2,
  "grid_col": 3,
  "score": 104.0,
  "peak_score": 118.0,
  "event_count": 6,
  "distinct_rules": 3,
  "sustained_seconds": 41.2,
  "status": "alert",
  "calibrated": true,
  "last_reason": "Head turned 34 degrees off own baseline, held 1.4 s",
  "occupied": true
}
```
- `status` $\in$ `["calm", "accumulating", "alert"]`
  - `calm`: score $< 40$
  - `accumulating`: score $40 - 99$
  - `alert`: score $\ge 100$

### Session
Represents an analysis or monitoring session.
```json
{
  "session_id": "sess_20260822_1030",
  "source": "datasets/cam2_hall_a.mp4",
  "state": "running",
  "progress": 0.42,
  "frames_processed": 12546,
  "frames_total": 29880,
  "duration_s": 996.0,
  "fps_processing": 8.4,
  "seats_tracked": 24,
  "events_total": 31,
  "alerts_total": 4,
  "config_hash": "a91f3c",
  "started_at": "2026-08-22T10:30:11+05:30",
  "ended_at": null,
  "error_message": null
}
```
- `state` $\in$ `["queued", "running", "done", "failed"]`

---

## 2. API Surface

| Method | Endpoint | Request Body / Params | Response |
|---|---|---|---|
| `GET` | `/api/health` | None | `{"ok": bool, "device": str, "model": str, "job_active": bool}` |
| `GET` | `/api/sessions` | None | `[Session]` |
| `POST` | `/api/sessions` | `{"source": str, "config_overrides": dict}` | `Session` |
| `GET` | `/api/sessions/{id}` | None | `Session` |
| `GET` | `/api/sessions/{id}/seats` | None | `[SeatState]` |
| `GET` | `/api/sessions/{id}/events` | `?since={event_id}` | `[Event]` |
| `GET` | `/api/sessions/{id}/timeline` | None | `{"timestamps": [...], "seats": {"S01": [...], ...}}` |
| `GET` | `/api/sessions/{id}/report.html` | None | Rendered HTML Report |
| `GET` | `/api/sessions/{id}/report.csv` | None | CSV Data Export |
| `GET` | `/api/stream/{id}` | None | `multipart/x-mixed-replace` MJPEG stream |
| `GET` | `/api/clips/{event_id}` | None | MP4 Evidence Clip Video Stream |
| `GET` | `/api/eval/{id}` | `?tolerance=3.0` | `{"precision": float, "recall": float, "f1": float, "fa_per_hour": float, ...}` |
| `POST` | `/api/upload` | Multipart form-data file | `{"source_path": str, "filename": str, "size": int}` |
