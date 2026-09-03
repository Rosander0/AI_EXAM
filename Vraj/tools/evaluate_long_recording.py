import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
"""End-to-End Evaluation of Long Exam Recording (CAMERA#.mp4)."""

import argparse
import csv
import json
import math
import time
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import cv2
import numpy as np

from sanket.calibration import SeatCalibrator, CalibrationState
from sanket.config import load_config
from sanket.detection import ObjectDetector
from sanket.features import FeatureExtractor, SeatFeatures
from sanket.hands import MediaPipeHandAnalyzer
from sanket.pose import PoseEstimator, KP, Person
from sanket.rules import RuleEngine, RuleFiring
from sanket.scoring import ScoringEngine, Event
from sanket.seats import SeatMap
from sanket.source import open_source
from sanket.store import SessionStore


def run_long_eval(
    video_path: str,
    gt_path: str,
    config_path: str = "config.yaml",
    seats_path: str = "seats_camera.yaml",
    max_time_s: float = 6000.0,
    frame_skip_override: Optional[int] = 4,
    pose_model_override: Optional[str] = "yolo11n-pose.pt",
    output_dir: str = "runs",
) -> Dict[str, Any]:
    cfg = load_config(config_path)
    if frame_skip_override:
        cfg.model["frame_skip"] = frame_skip_override
    if pose_model_override:
        cfg.model["pose_weights"] = pose_model_override
        cfg.model["imgsz"] = 480

    gt_labels = json.loads(Path(gt_path).read_text(encoding="utf-8"))
    src = open_source(video_path, config_source=cfg.source)

    estimator = PoseEstimator(cfg)
    seat_map = SeatMap(cfg, manual_seats_path=seats_path)
    feature_extractor = FeatureExtractor(cfg)
    rule_engine = RuleEngine(cfg)

    store = SessionStore()
    session_id = f"sess_long_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    scoring_engine = ScoringEngine(cfg, session_id=session_id)

    hand_analyzer = MediaPipeHandAnalyzer(cfg) if cfg.get("hands", {}).get("enabled", True) else None
    calibrators: Dict[str, SeatCalibrator] = {}
    for sid in seat_map.seats:
        calibrators[sid] = SeatCalibrator(sid, cfg)

    # Tracking metrics
    seat_rebind_counts: Dict[str, int] = defaultdict(int)
    last_seat_tracks: Dict[str, Optional[int]] = {}
    
    # Feature histories inside labelled windows for NEAR vs FLAT vs STRUCTURAL analysis
    label_diagnostics: Dict[str, Dict[str, Any]] = {}
    for lbl in gt_labels:
        label_diagnostics[lbl["label_id"]] = {
            "label": lbl,
            "max_deviation": 0.0,
            "max_held_duration": 0.0,
            "calibrated": False,
            "firings": [],
            "all_features": []
        }

    # Timeline of scores and baselines every 5 seconds
    timeline_records: List[Dict[str, Any]] = []
    all_events: List[Event] = []
    
    start_t0 = time.perf_counter()
    frames_processed = 0

    print(f"[INFO] Starting long evaluation run on {video_path}...")
    with src:
        for frame in src:
            if frame.t > max_time_s:
                break
            frames_processed += 1
            if frames_processed % 3000 == 0:
                elapsed_wall = time.perf_counter() - start_t0
                fps_proc = frames_processed / elapsed_wall if elapsed_wall > 0 else 0
                print(f"  [PROGRESS] t={frame.t/60.0:.1f}m / {max_time_s/60.0:.1f}m ({frames_processed} frames) | Throughput: {fps_proc:.1f} FPS")

            # 1. Pose estimation
            persons = estimator.track(frame)

            # 2. Seat assignments
            seat_assignments, staff_persons = seat_map.update(persons, frame.t, frame.image.shape)

            # Check track rebinds
            for sid, seat in seat_map.seats.items():
                curr_tid = seat.current_track_id
                prev_tid = last_seat_tracks.get(sid)
                if curr_tid is not None and prev_tid is not None and curr_tid != prev_tid:
                    seat_rebind_counts[sid] += 1
                last_seat_tracks[sid] = curr_tid

            # Feed calibrators
            for sid, p in seat_assignments.items():
                if p is not None and sid in calibrators:
                    seat_obj = seat_map.seats[sid]
                    calibrators[sid].add_sample(p, seat_obj, frame.t, seat_obj.score)
                    seat_obj.calibrated = calibrators[sid].is_calibrated

            unassigned = [p for p in persons if id(p) not in {id(x) for x in seat_assignments.values() if x is not None}]

            # 3. Geometric features
            seat_features = feature_extractor.extract_features(
                seat_assignments=seat_assignments,
                staff_persons=staff_persons,
                seat_map=seat_map,
                calibrators=calibrators,
                t=frame.t,
            )

            # 4. Rules
            firings_by_seat: Dict[str, List[RuleFiring]] = defaultdict(list)
            for sid, feats in seat_features.items():
                cal = calibrators.get(sid)
                is_cal = cal is not None and cal.state == CalibrationState.CALIBRATING
                is_failed = cal is not None and cal.state == CalibrationState.FAILED
                p = seat_assignments.get(sid)
                tid = p.track_id if p else None

                seat_firings = rule_engine.evaluate_seat(
                    features=feats,
                    track_id=tid,
                    frame_index=frame.index,
                    is_calibrating=is_cal,
                    is_staff=False,
                    baseline_unavailable=is_failed,
                )
                if seat_firings:
                    firings_by_seat[sid].extend(seat_firings)

            # 5. Hand analyzer (if enabled)
            if hand_analyzer and (frame.index % 20 == 0):
                frame_rgb = cv2.cvtColor(frame.image, cv2.COLOR_BGR2RGB)
                seat_hands, hand_firings = hand_analyzer.analyze_frame(
                    frame_rgb=frame_rgb,
                    seat_assignments=seat_assignments,
                    t=frame.t,
                    frame_index=frame.index,
                    unassigned_persons=unassigned,
                )
                for hf in hand_firings:
                    firings_by_seat[hf.seat_id].append(hf)

            # 6. Scoring engine
            frame_events = scoring_engine.update(seat_map.seats, firings_by_seat, frame.t)
            if frame_events:
                all_events.extend(frame_events)

            # Diagnostic logging for GT labels
            for lbl in gt_labels:
                lid = lbl["label_id"]
                lsid = lbl["seat_id"]
                l_rule = lbl["rule"]
                t_st = lbl["t_start"]
                t_en = lbl["t_end"]
                if (t_st - 3.0) <= frame.t <= (t_en + 3.0):
                    diag = label_diagnostics[lid]
                    cal = calibrators.get(lsid)
                    diag["calibrated"] = cal.is_calibrated if cal else False
                    feats = seat_features.get(lsid)
                    if feats:
                        if l_rule == "head_turn" and feats.head_turn_deviation is not None:
                            diag["max_deviation"] = max(diag["max_deviation"], feats.head_turn_deviation)
                        elif l_rule == "lap_gazing" and feats.nose_displacement is not None:
                            diag["max_deviation"] = max(diag["max_deviation"], feats.nose_displacement)
                        elif l_rule == "turning_back" and feats.shoulder_span_ratio is not None:
                            diag["max_deviation"] = max(diag["max_deviation"], 1.0 - feats.shoulder_span_ratio)

                    for sf in firings_by_seat.get(lsid, []):
                        diag["firings"].append({
                            "t": frame.t,
                            "rule": sf.rule,
                            "reason": sf.reason,
                            "points": sf.points
                        })

            # Record timeline every 5s
            if int(frame.t) % 5 == 0 and (not timeline_records or timeline_records[-1]["t"] != int(frame.t)):
                rec = {"t": int(frame.t)}
                for sid, seat in seat_map.seats.items():
                    cal = calibrators.get(sid)
                    rec[f"{sid}_score"] = round(seat.score, 1)
                    rec[f"{sid}_peak"] = round(seat.peak_score, 1)
                    rec[f"{sid}_asym_base"] = round(cal.baselines.get("ear_nose_asymmetry", 0.0), 3) if cal else 0.0
                    rec[f"{sid}_span_base"] = round(cal.baselines.get("shoulder_span", 0.0), 1) if cal else 0.0
                timeline_records.append(rec)

    total_wall_time = time.perf_counter() - start_t0
    mean_fps = frames_processed / total_wall_time if total_wall_time > 0 else 0.0

    print(f"[INFO] Inference finished: {frames_processed} frames in {total_wall_time:.1f}s ({mean_fps:.1f} FPS)")

    # Match GT labels
    evaluated_labels: List[Dict[str, Any]] = []
    caught_count = 0
    caught_weak_count = 0
    near_count = 0
    flat_count = 0
    structural_count = 0

    for lbl in gt_labels:
        lid = lbl["label_id"]
        diag = label_diagnostics[lid]
        lsid = lbl["seat_id"]
        l_rule = lbl["rule"]
        t_st = lbl["t_start"]
        t_en = lbl["t_end"]

        # Check emitted events
        matched_events = [
            e for e in all_events
            if e.seat_id == lsid and (t_st - 5.0) <= e.t_end and e.t_start <= (t_en + 5.0)
        ]

        seat_score_in_window = 0.0
        for rec in timeline_records:
            if t_st <= rec["t"] <= t_en:
                seat_score_in_window = max(seat_score_in_window, rec.get(f"{lsid}_score", 0.0))

        if matched_events:
            has_crit = any(e.severity == "critical" or e.score_after >= 100.0 for e in matched_events)
            if has_crit:
                status = "CAUGHT"
                caught_count += 1
            else:
                status = "CAUGHT_WEAK"
                caught_weak_count += 1
            miss_class = "NONE"
        else:
            # Classify miss
            if not diag["calibrated"]:
                status = "STRUCTURAL"
                miss_class = "STRUCTURAL (Seat not yet calibrated / no baseline)"
                structural_count += 1
            elif diag["max_deviation"] >= 2.0 or len(diag["firings"]) > 0:
                status = "NEAR"
                miss_class = f"NEAR (Deviation reached {diag['max_deviation']:.2f}, but duration insufficient)"
                near_count += 1
            else:
                status = "FLAT"
                miss_class = f"FLAT (Feature stayed near baseline, max dev {diag['max_deviation']:.2f})"
                flat_count += 1

        evaluated_labels.append({
            "label_id": lid,
            "raw_timestamp": lbl["raw_timestamp"],
            "t_start": t_st,
            "t_end": t_en,
            "actor": lbl["reviewer_actor"],
            "seat_id": lsid,
            "event_type": lbl["event_type"],
            "rule": l_rule,
            "description": lbl["description"],
            "status": status,
            "miss_classification": miss_class,
            "matched_events_count": len(matched_events),
            "peak_score_window": seat_score_in_window,
            "matched_reasons": [e.reason for e in matched_events]
        })

    # Find outside-window firings
    outside_window_events: List[Dict[str, Any]] = []
    for evt in all_events:
        is_inside_gt = False
        for lbl in gt_labels:
            if evt.seat_id == lbl["seat_id"] and (lbl["t_start"] - 5.0) <= evt.t_end and evt.t_start <= (lbl["t_end"] + 5.0):
                is_inside_gt = True
                break
        if not is_inside_gt:
            outside_window_events.append({
                "event_id": evt.event_id,
                "t_start": evt.t_start,
                "t_end": evt.t_end,
                "seat_id": evt.seat_id,
                "rule": evt.rule,
                "severity": evt.severity,
                "points": evt.points,
                "score_after": evt.score_after,
                "reason": evt.reason,
            })

    total_duration_hours = max_time_s / 3600.0
    fa_per_hour = len(outside_window_events) / total_duration_hours if total_duration_hours > 0 else 0.0

    # Event-type breakdown
    event_type_summary: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for el in evaluated_labels:
        etype = el["event_type"]
        stat = el["status"]
        event_type_summary[etype][stat] += 1
        event_type_summary[etype]["TOTAL"] += 1

    results = {
        "session_id": session_id,
        "frames_processed": frames_processed,
        "duration_hours": round(total_duration_hours, 2),
        "processing_fps": round(mean_fps, 1),
        "rebind_counts": dict(seat_rebind_counts),
        "summary": {
            "total_labels": len(gt_labels),
            "caught": caught_count,
            "caught_weak": caught_weak_count,
            "near": near_count,
            "flat": flat_count,
            "structural": structural_count,
            "outside_window_firings": len(outside_window_events),
            "outside_window_fa_per_hour": round(fa_per_hour, 2),
        },
        "labels": evaluated_labels,
        "event_type_breakdown": dict(event_type_summary),
        "outside_window_events": outside_window_events,
        "timeline": timeline_records,
    }

    out_p = Path(output_dir) / f"long_eval_{session_id}.json"
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nSaved full evaluation results to {out_p}")
    return results


if __name__ == "__main__":
    res = run_long_eval(
        video_path=r"C:\Users\Vraj\Documents\Drishti_AI\DRISHTI AI DEXIT GLobal Datasets\CAMERA#.mp4",
        gt_path="datasets/labels/CAMERA#.json",
        max_time_s=6000.0,
    )
