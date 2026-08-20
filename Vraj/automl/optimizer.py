"""
SANKET Auto-ML Self-Tuning Pipeline
===================================
Self-contained hyperparameter optimization module using Optuna.
This module evaluates SANKET over ground-truth labeled videos and learns optimal
detection thresholds without manual intervention.

Usage:
  python automl/optimizer.py
"""

import json
import subprocess
import time
import sqlite3
import yaml
from pathlib import Path

try:
    import optuna
except ImportError:
    print("[ERROR] Optuna is required. Run: pip install optuna")
    exit(1)

# Base Paths (Relative to project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
GROUND_TRUTH_FILE = Path(__file__).resolve().parent / "ground_truth.json"
CONFIG_FILE = PROJECT_ROOT / "config.yaml"
DB_PATH = PROJECT_ROOT / "data" / "sanket.db"

# Load ground truth
if not GROUND_TRUTH_FILE.is_file():
    print(f"[ERROR] Ground truth file not found: {GROUND_TRUTH_FILE}")
    exit(1)

with open(GROUND_TRUTH_FILE, "r", encoding="utf-8") as f:
    DATASET = json.load(f)


def update_config(params: dict):
    """Updates config.yaml with trial parameters."""
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Apply tuned parameters
    if "objects_conf" in params:
        config["objects"]["conf"] = float(params["objects_conf"])
    if "lap_gazing_disp" in params:
        config["rules"]["lap_gazing"]["displacement_threshold"] = float(params["lap_gazing_disp"])
    if "lap_gazing_dur" in params:
        config["rules"]["lap_gazing"]["min_duration_seconds"] = float(params["lap_gazing_dur"])
    if "decay_rate" in params:
        config["scoring"]["decay_rate"] = float(params["decay_rate"])

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, sort_keys=False)


def get_last_session_alerts() -> int:
    """Reads SQLite DB to get alerts_total of the most recent run."""
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT alerts_total FROM sessions ORDER BY started_at DESC LIMIT 1").fetchone()
        conn.close()
        return row["alerts_total"] if row else 0
    except Exception as e:
        print(f"[WARN] Error reading DB: {e}")
        return 0


def objective(trial: optuna.Trial) -> float:
    """Optuna objective function: minimizes false positives & false negatives."""
    params = {
        "objects_conf": trial.suggest_float("objects_conf", 0.20, 0.50),
        "lap_gazing_disp": trial.suggest_float("lap_gazing_disp", 0.20, 0.50),
        "lap_gazing_dur": trial.suggest_float("lap_gazing_dur", 1.5, 4.0),
        "decay_rate": trial.suggest_float("decay_rate", 0.8, 3.0),
    }

    print(f"\n{'='*60}")
    print(f"[Auto-ML] TRIAL {trial.number} | Evaluating Hyperparameters:")
    for k, v in params.items():
        print(f"  • {k}: {v:.3f}")
    print(f"{'='*60}")

    update_config(params)

    total_error = 0.0

    for rel_video_path, labels in DATASET.items():
        video_path = PROJECT_ROOT / rel_video_path
        expected = labels.get("expected_alert", True)

        if not video_path.is_file():
            print(f"  [SKIP] Video file not found: {video_path.name}")
            continue

        print(f"  Testing {video_path.name} (Expected Cheating Alert: {expected})...")

        # Run SANKET headlessly for 350 frames (~12s) to evaluate quickly
        cmd = [
            "python", str(PROJECT_ROOT / "main.py"),
            "--source", str(video_path),
            "--max-frames", "350",
        ]

        subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        alerts_generated = get_last_session_alerts()
        predicted = alerts_generated > 0

        if predicted != expected:
            print(f"    ❌ MISMATCH: Predicted Alert={predicted}, Expected={expected}")
            total_error += 1.0
        else:
            print(f"    ✅ PASS: Correctly predicted (Alerts={alerts_generated})")

    print(f"Trial {trial.number} Result -> Total Classification Loss: {total_error}")
    return total_error


def run():
    print("\n=======================================================")
    print(" SANKET Auto-ML Self-Optimization Pipeline ")
    print("=======================================================\n")
    print(f"Project Root   : {PROJECT_ROOT}")
    print(f"Dataset Items  : {len(DATASET)}")
    print(f"Output Config  : {CONFIG_FILE}\n")

    study = optuna.create_study(direction="minimize")
    study.optimize(objective, n_trials=10)

    print("\n" + "=" * 60)
    print(" OPTIMIZATION RUN FINISHED ")
    print("=" * 60)
    print("Optimal Hyperparameters:")
    for k, v in study.best_params.items():
        print(f"  • {k}: {v:.4f}")
    print(f"Minimum Loss Achieved: {study.best_value}")

    print("\nApplying optimal settings to config.yaml...")
    update_config(study.best_params)
    print("✅ Configuration successfully evolved and saved!")


if __name__ == "__main__":
    run()
