"""Unit and integration tests for SANKET Prompt 9 (Backend API)."""

from fastapi.testclient import TestClient
import pytest
from server.app import app

client = TestClient(app)


def test_api_health_endpoint():
    """Verify /api/health returns ok, device, and active job status."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "device" in data
    assert "model" in data
    assert isinstance(data["job_active"], bool)


def test_api_sessions_list_and_404():
    """Verify /api/sessions returns list, and /api/sessions/{id} returns 404 on missing session."""
    # List sessions
    response = client.get("/api/sessions")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

    # Missing session returns valid 404 JSON
    res_404 = client.get("/api/sessions/sess_nonexistent_99999")
    assert res_404.status_code == 404
    assert "detail" in res_404.json()


def test_api_create_session_bad_source():
    """Verify POST /api/sessions with invalid file returns 400 Bad Request JSON."""
    response = client.post("/api/sessions", json={"source": "nonexistent_file_path.mp4"})
    assert response.status_code == 400
    assert "Video file not found" in response.json()["detail"]
