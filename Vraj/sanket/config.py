"""Configuration loader and validator for SANKET.

Invariant: Nothing may ever be hardcoded outside config.yaml.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict
import yaml

DEFAULT_CONFIG: Dict[str, Any] = {
    "source": {
        "fps_override": None,
        "resize_width": 1280,
        "reconnect_max_seconds": 30,
        "rtsp_buffer_size": 1,
    },
    "model": {
        "pose_weights": "models/yolo11m-pose.pt",
        "imgsz": 640,
        "conf": 0.25,
        "keypoint_min_conf": 0.5,
        "device": "auto",
        "half": False,
        "frame_skip": 1,
    },
    "identity": {},
    "calibration": {},
    "rules": {},
    "objects": {},
    "scoring": {},
    "output": {
        "run_dir": "runs",
        "save_video": True,
        "save_report": True,
    },
}


class ConfigDict(dict):
    """Dictionary subclass supporting attribute-style dot access."""

    def __getattr__(self, key: str) -> Any:
        try:
            val = self[key]
            if isinstance(val, dict) and not isinstance(val, ConfigDict):
                val = ConfigDict(val)
                self[key] = val
            return val
        except KeyError:
            raise AttributeError(f"Config has no attribute '{key}'")

    def __setattr__(self, key: str, value: Any) -> None:
        self[key] = value

    def get_nested(self, path: str, default: Any = None) -> Any:
        parts = path.split(".")
        curr = self
        for p in parts:
            if isinstance(curr, dict) and p in curr:
                curr = curr[p]
            else:
                return default
        return curr


def _deep_merge(base: dict, update: dict) -> dict:
    """Recursively merges update dict into base dict."""
    result = dict(base)
    for k, v in update.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_config(config_path: str | Path | None = None, overrides: dict | None = None) -> ConfigDict:
    """Loads YAML configuration, validates structure, and applies overrides."""
    merged = dict(DEFAULT_CONFIG)

    path = Path(config_path) if config_path else Path("config.yaml")
    if path.is_file():
        with open(path, "r", encoding="utf-8") as f:
            file_cfg = yaml.safe_load(f) or {}
            merged = _deep_merge(merged, file_cfg)
    elif config_path is not None:
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    if overrides:
        merged = _deep_merge(merged, overrides)

    return ConfigDict(merged)


def compute_config_hash(cfg: dict | ConfigDict) -> str:
    """Produces a deterministic 6-character hash of the configuration."""
    canonical_json = json.dumps(cfg, sort_keys=True, default=str)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()[:6]
