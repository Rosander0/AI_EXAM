"""Evaluation harness for SANKET.

Matches predicted events with ground truth intervals using temporal IoU.
Computes Precision, Recall, F1, and False-Alarms-per-Hour.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

from sanket.store import SessionStore


def temporal_iou(t1_start: float, t1_end: float, t2_start: float, t2_end: float) -> float:
    """Calculates 1D temporal Intersection over Union between two intervals."""
    inter_start = max(t1_start, t2_start)
    inter_end = min(t1_end, t2_end)
    intersection = max(0.0, inter_end - inter_start)

    union_start = min(t1_start, t2_start)
    union_end = max(t1_end, t2_end)
    union = max(1e-6, union_end - union_start)

    return float(intersection / union)


def evaluate_session(
    session_id: str,
    ground_truth_path: Path | str,
    store: Optional[SessionStore] = None,
    iou_thresh: float = 0.3,
    output_dir: Path | str = "runs",
) -> Dict[str, Any]:
    """Computes precision, recall, and false-alarm metrics against ground truth."""
    if store is None:
        store = SessionStore()

    session = store.get_session(session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found.")

    events = store.get_events(session_id)
    gt_file = Path(ground_truth_path)
    if not gt_file.is_file():
        raise FileNotFoundError(f"Ground truth file not found: {gt_file}")

    ground_truth: List[Dict[str, Any]] = json.loads(gt_file.read_text(encoding="utf-8"))

    # Match predicted events to ground truth
    matched_gt = set()
    matched_pred = set()

    for p_idx, pred in enumerate(events):
        p_sid = pred["seat_id"]
        p_start = pred["t_start"]
        p_end = pred["t_end"]

        best_gt_idx = None
        best_iou = 0.0

        for g_idx, gt in enumerate(ground_truth):
            if g_idx in matched_gt:
                continue

            # Check seat match (or wildcard)
            if gt.get("seat_id") and gt["seat_id"] != p_sid:
                continue

            iou = temporal_iou(p_start, p_end, gt["t_start"], gt["t_end"])
            if iou >= iou_thresh and iou > best_iou:
                best_iou = iou
                best_gt_idx = g_idx

        if best_gt_idx is not None:
            matched_gt.add(best_gt_idx)
            matched_pred.add(p_idx)

    tp = len(matched_pred)
    fp = len(events) - tp
    fn = len(ground_truth) - len(matched_gt)

    precision = (tp / (tp + fp)) if (tp + fp) > 0 else 1.0
    recall = (tp / (tp + fn)) if (tp + fn) > 0 else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    duration_h = (session["duration_s"] or 1.0) / 3600.0
    fa_per_hour = (fp / duration_h) if duration_h > 0 else 0.0

    metrics = {
        "session_id": session_id,
        "ground_truth_file": str(gt_file),
        "total_ground_truth": len(ground_truth),
        "total_predicted_events": len(events),
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "duration_hours": round(duration_h, 4),
        "false_alarms_per_hour": round(fa_per_hour, 2),
    }

    out_d = Path(output_dir)
    out_d.mkdir(parents=True, exist_ok=True)
    out_json = out_d / f"eval_{session_id}.json"
    out_json.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="SANKET Evaluation Harness")
    parser.add_argument("--session", type=str, required=True, help="Session ID to evaluate")
    parser.add_argument("--ground-truth", type=str, required=True, help="Path to ground-truth labels JSON")
    parser.add_argument("--iou", type=float, default=0.3, help="Temporal IoU threshold (default 0.3)")
    args = parser.parse_args()

    try:
        metrics = evaluate_session(
            session_id=args.session,
            ground_truth_path=args.ground_truth,
            iou_thresh=args.iou,
        )

        print("\n" + "=" * 70)
        print(f"--- SANKET EVALUATION REPORT: {args.session} ---")
        print("=" * 70)
        print(f"Ground Truth Events       : {metrics['total_ground_truth']}")
        print(f"Predicted Events          : {metrics['total_predicted_events']}")
        print(f"True Positives (TP)       : {metrics['true_positives']}")
        print(f"False Positives (FP)      : {metrics['false_positives']}")
        print(f"False Negatives (FN)      : {metrics['false_negatives']}")
        print(f"Precision                 : {metrics['precision'] * 100:.1f}%")
        print(f"Recall                    : {metrics['recall'] * 100:.1f}%")
        print(f"F1 Score                  : {metrics['f1_score']:.3f}")
        print(f"False-Alarms-per-Hour     : {metrics['false_alarms_per_hour']:.1f} FA/hr")
        print("=" * 70 + "\n")
        return 0
    except Exception as e:
        print(f"Evaluation failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
