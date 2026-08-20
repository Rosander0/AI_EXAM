"""Unit tests for SANKET Prompt 10 (React 18 Invigilator Dashboard)."""

import json
from pathlib import Path
from fastapi.testclient import TestClient
import pytest
from server.app import app

client = TestClient(app)


def test_react_dashboard_static_files_served():
    """Verify FastAPI serves React 18 index.html, react-app.css, react-app.js, and vendored React scripts."""
    # Root index.html
    res_index = client.get("/")
    assert res_index.status_code == 200
    assert "SANKET" in res_index.text
    assert '<div id="root"></div>' in res_index.text

    # react-app.css
    res_css = client.get("/static/react-app.css")
    assert res_css.status_code == 200
    assert "--bg-main" in res_css.text

    # react-app.js
    res_js = client.get("/static/react-app.js")
    assert res_js.status_code == 200
    assert "function App" in res_js.text

    # Vendored React scripts
    res_react = client.get("/static/react.min.js")
    assert res_react.status_code == 200
    assert len(res_react.content) > 1000


def test_dashboard_copy_invariants():
    """Invariant Check: The words 'cheating' and 'caught' must not appear anywhere in UI code."""
    web_dir = Path("web")
    for fpath in [web_dir / "index.html", web_dir / "static" / "react-app.css", web_dir / "static" / "react-app.js"]:
        text = fpath.read_text(encoding="utf-8").lower()
        assert "cheating" not in text, f"Forbidden word 'cheating' found in {fpath}"
        assert "caught" not in text, f"Forbidden word 'caught' found in {fpath}"


def test_dashboard_mock_data_validity():
    """Verify mock files exist and have valid structure for offline demo testing."""
    mock_dir = Path("web/mock")
    session_mock = json.loads((mock_dir / "session.json").read_text(encoding="utf-8"))
    seats_mock = json.loads((mock_dir / "seats.json").read_text(encoding="utf-8"))
    events_mock = json.loads((mock_dir / "events.json").read_text(encoding="utf-8"))

    assert session_mock["session_id"] == "sess_mock_demo"
    assert len(seats_mock) == 4
    assert len(events_mock) == 3
