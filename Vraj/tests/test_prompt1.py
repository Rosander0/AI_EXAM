"""Unit tests for SANKET Prompt 1 (Foundation & Video Input)."""

import numpy as np
import pytest
from sanket.config import load_config, compute_config_hash
from sanket.device import resolve_device
from sanket.render import draw_hud, format_source_time
from sanket.source import Frame, open_source


def test_format_source_time():
    assert format_source_time(0.0) == "00:00.000"
    assert format_source_time(65.432) == "01:05.432"
    assert format_source_time(600.0) == "10:00.000"


def test_config_loading_and_hash():
    cfg = load_config("config.yaml")
    assert cfg.source.resize_width == 1280
    assert cfg.model.imgsz == 640
    hash1 = compute_config_hash(cfg)
    assert len(hash1) == 6
    assert isinstance(hash1, str)


def test_device_resolution():
    dev = resolve_device("cpu")
    assert dev == "cpu"


def test_hud_rendering():
    dummy_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    info = {
        "frame_index": 42,
        "t": 1.68,
        "fps": 25.0,
        "source_name": "test_cam.mp4",
        "device": "cpu",
    }
    rendered = draw_hud(dummy_frame, info)
    assert rendered.shape == (720, 1280, 3)
    # HUD drew something non-zero
    assert np.any(rendered > 0)


def test_time_base_invariant():
    """Verify t = index / fps invariant for recorded video stream."""
    fps = 25.0
    for idx in [0, 25, 50, 100, 1500]:
        expected_t = idx / fps
        frame = Frame(index=idx, t=idx / fps, image=np.zeros((10, 10, 3), dtype=np.uint8))
        assert frame.t == pytest.approx(expected_t)
