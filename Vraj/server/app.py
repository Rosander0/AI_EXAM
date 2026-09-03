"""FastAPI Backend Application for SANKET.

CRITICAL INVARIANTS:
1. Implements frozen DATA_CONTRACT.md endpoints exactly.
2. Returns valid JSON on failure, never a bare 500 traceback.
3. Serves frontend static files from web/ at root path.
4. CORS restricted to localhost.
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional
import cv2
from fastapi import FastAPI, File, HTTPException, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from sanket.config import load_config
from sanket.device import resolve_device
from sanket.store import SessionStore
from server.jobs import JobRunner
from server.schemas import (
    EventSchema,
    HealthResponse,
    SeatStateSchema,
    SessionCreateRequest,
    SessionSchema,
    StaffStateSchema,
    StaffEventSchema,
)
from server.streamer import streamer

app = FastAPI(
    title="SANKET API",
    description="AI Exam Invigilation Assistant Backend",
    version="1.0.0",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

store = SessionStore()
runner = JobRunner(store)
cfg = load_config()


@app.get("/api/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Returns system health, device, and active worker state."""
    device = resolve_device(cfg.model.get("device", "auto"))
    return HealthResponse(
        ok=True,
        device=device,
        model=cfg.model.get("pose_weights", "yolo11m-pose.pt"),
        job_active=runner.is_busy(),
    )


@app.get("/api/sessions", response_model=List[SessionSchema])
def list_sessions() -> List[SessionSchema]:
    """Lists all historical and active monitoring sessions."""
    with store._get_connection() as conn:
        rows = conn.execute("SELECT * FROM sessions ORDER BY started_at DESC").fetchall()
        return [SessionSchema(**dict(r)) for r in rows]


@app.post("/api/sessions", response_model=SessionSchema, status_code=status.HTTP_201_CREATED)
def create_session(payload: SessionCreateRequest) -> SessionSchema:
    """Starts a new invigilation session in a background thread."""
    if runner.is_busy():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Another session is currently active: {runner.active_session_id}",
        )

    # Validate source
    source_path = payload.source
    if not source_path.startswith(("rtsp://", "http://", "https://")) and not source_path.isdigit():
        if not Path(source_path).is_file():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Video file not found: {source_path}",
            )

    try:
        session_rec = runner.start_session(source_path, config_overrides=payload.config_overrides)
        return SessionSchema(**session_rec)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/api/sessions/{session_id}", response_model=SessionSchema)
def get_session_by_id(session_id: str) -> SessionSchema:
    """Retrieves session progress and execution state."""
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session {session_id} not found")
    return SessionSchema(**session)


@app.post("/api/sessions/{session_id}/stop")
def stop_session_by_id(session_id: str) -> Dict[str, Any]:
    """Stops the active invigilation session immediately."""
    if runner.is_busy():
        runner.stop_session()
        return {"ok": True, "message": f"Session {session_id} halt requested."}
    return {"ok": True, "message": "No active session to stop."}


@app.post("/api/sessions/stop")
def stop_active_session() -> Dict[str, Any]:
    """Stops whatever session is currently active."""
    if runner.is_busy():
        runner.stop_session()
        return {"ok": True, "message": "Session halt requested."}
    return {"ok": True, "message": "No active session."}


@app.get("/api/sessions/{session_id}/seats", response_model=List[SeatStateSchema])
def get_session_seats(session_id: str) -> List[SeatStateSchema]:
    """Retrieves per-seat real-time state and scores."""
    seats = store.get_seat_states(session_id)
    return [
        SeatStateSchema(
            seat_id=s["seat_id"],
            grid_row=s["grid_row"],
            grid_col=s["grid_col"],
            score=s["score"],
            peak_score=s["peak_score"],
            event_count=s["event_count"],
            distinct_rules=s["distinct_rules"],
            sustained_seconds=s["sustained_seconds"],
            status=s["status"],
            calibrated=bool(s["calibrated"]),
            last_reason=s["last_reason"],
            occupied=bool(s["occupied"]),
        )
        for s in seats
    ]


@app.get("/api/sessions/{session_id}/events", response_model=List[EventSchema])
def get_session_events(
    session_id: str,
    since: Optional[str] = Query(None, description="Event ID cursor for incremental polling"),
) -> List[EventSchema]:
    """Incremental polling endpoint for newly raised events."""
    events = store.get_events(session_id, since_id=since)
    return [EventSchema(**e) for e in events]


@app.get("/api/sessions/{session_id}/staff", response_model=List[StaffStateSchema])
def get_session_staff(session_id: str) -> List[StaffStateSchema]:
    """Retrieves staff member profiles and supervision metrics."""
    staff = store.get_staff_states(session_id)
    return [StaffStateSchema(**s) for s in staff]


@app.get("/api/sessions/{session_id}/staff/events", response_model=List[StaffEventSchema])
def get_session_staff_events(session_id: str) -> List[StaffEventSchema]:
    """Retrieves staff supervision observation events."""
    events = store.get_staff_events(session_id)
    return [StaffEventSchema(**e) for e in events]



@app.get("/api/sessions/{session_id}/timeline")
def get_session_timeline(session_id: str) -> Dict[str, Any]:
    """Retrieves score timeline samples for inline SVG rendering."""
    with store._get_connection() as conn:
        rows = conn.execute(
            "SELECT seat_id, t, score FROM seat_timeline WHERE session_id = ? ORDER BY t ASC",
            (session_id,),
        ).fetchall()

    timeline_by_seat: Dict[str, List[Dict[str, float]]] = {}
    timestamps: List[float] = []

    for r in rows:
        sid = r["seat_id"]
        t = r["t"]
        score = r["score"]
        if sid not in timeline_by_seat:
            timeline_by_seat[sid] = []
        timeline_by_seat[sid].append({"t": t, "score": score})
        if not timestamps or timestamps[-1] != t:
            timestamps.append(t)

    return {
        "session_id": session_id,
        "timestamps": timestamps,
        "seats": timeline_by_seat,
    }


@app.get("/api/sessions/{session_id}/report.html")
def get_session_report_html(session_id: str) -> Response:
    """Returns rendered invigilator HTML report."""
    report_file = Path("runs") / f"report_{session_id}.html"
    if not report_file.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="HTML report not found.")
    return HTMLResponse(content=report_file.read_text(encoding="utf-8"))


@app.get("/api/sessions/{session_id}/report.csv")
def get_session_report_csv(session_id: str) -> Response:
    """Returns raw CSV data export."""
    csv_file = Path("runs") / f"report_{session_id}.csv"
    if not csv_file.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CSV report not found.")
    return FileResponse(csv_file, media_type="text/csv", filename=f"report_{session_id}.csv")


@app.get("/api/stream/{session_id}")
def stream_mjpeg(session_id: str) -> StreamingResponse:
    """Serves real-time annotated video over multipart MJPEG."""
    return StreamingResponse(
        streamer.generate_mjpeg(session_id=session_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/api/clips/{event_id}")
def get_evidence_clip(event_id: str) -> FileResponse:
    """Serves mp4 evidence clip for the given event."""
    clip_file = Path("clips") / f"{event_id}.mp4"
    if not clip_file.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found.")
    return FileResponse(clip_file, media_type="video/mp4")


@app.get("/api/thumbs/{event_id}")
def get_evidence_thumb(event_id: str) -> FileResponse:
    """Serves jpg thumbnail evidence for the given event."""
    thumb_file = Path("clips") / f"{event_id}_thumb.jpg"
    if not thumb_file.is_file():
        thumb_file = Path("thumbs") / f"{event_id}.jpg"
    if not thumb_file.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thumbnail not found.")
    return FileResponse(thumb_file, media_type="image/jpeg")


@app.get("/api/eval/{session_id}")
def get_session_evaluation(session_id: str) -> Dict[str, Any]:
    """Returns evaluation metrics if ground-truth labels exist."""
    events = store.get_events(session_id)
    session = store.get_session(session_id)
    duration_h = (session["duration_s"] or 1.0) / 3600.0
    alerts_count = sum(1 for e in events if e["severity"] == "critical")
    fa_per_hour = alerts_count / duration_h if duration_h > 0 else 0.0

    return {
        "session_id": session_id,
        "total_events": len(events),
        "critical_alerts": alerts_count,
        "fa_per_hour": round(fa_per_hour, 2),
        "duration_hours": round(duration_h, 3),
        "ground_truth_available": False,
        "notice": "Organiser dataset evaluated for false-alarm baseline.",
    }


@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Accepts uploaded video, validates video headers, and returns usable source path."""
    upload_dir = Path("datasets/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)

    dest_path = upload_dir / file.filename
    with open(dest_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Validate that OpenCV can open it as a video
    cap = cv2.VideoCapture(str(dest_path))
    if not cap.isOpened():
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is not a valid playable video.")
    cap.release()

    return {
        "source_path": str(dest_path),
        "filename": file.filename,
        "size": dest_path.stat().st_size,
    }


# Mount static files from web/ if directory exists
web_dir = Path("web")
web_dir.mkdir(parents=True, exist_ok=True)
app.mount("/", StaticFiles(directory=str(web_dir), html=True), name="web")
