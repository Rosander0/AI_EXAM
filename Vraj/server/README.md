# SANKET Backend API Server

FastAPI server wrapping the SANKET invigilation pipeline and serving the web dashboard.

---

## Starting the Server

```bash
uvicorn server.app:app --host 127.0.0.1 --port 8000 --reload
```

The server will be accessible at:
- **Dashboard UI**: `http://localhost:8000/`
- **Interactive API Docs**: `http://localhost:8000/docs`
- **Health Check**: `http://localhost:8000/api/health`

---

## Key Endpoints

- `GET /api/health` — Hardware device, model info, and active job status.
- `GET /api/sessions` — List all sessions.
- `POST /api/sessions` — Start an engine run in a background thread.
- `GET /api/sessions/{id}/seats` — Real-time per-seat scores and status.
- `GET /api/sessions/{id}/events?since={event_id}` — Incremental event polling.
- `GET /api/sessions/{id}/timeline` — Time-series scores for inline SVG chart.
- `GET /api/stream/{id}` — Live MJPEG stream of annotated video.
- `POST /api/upload` — Upload candidate exam footage.
