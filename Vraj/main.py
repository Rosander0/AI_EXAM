"""SANKET CLI Entrypoint (Prompt 8: Session Store & Reports).

Usage:
  python main.py --source <spec> [--show] [--max-frames N] [--config path]
                 [--skeleton-only] [--seats <yaml>] [--show-anchors]
                 [--show-features] [--dump-features] [--no-objects]
                 [--disable-rule <name>] [--threshold <n>] [--decay <n>]
"""

from __future__ import annotations

import argparse
from collections import defaultdict, deque
import csv
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Set
import cv2
import numpy as np

from sanket.calibration import SeatCalibrator, CalibrationState
from sanket.clips import ClipExtractor
from sanket.config import load_config, compute_config_hash
from sanket.detection import ObjectDetector, DetectedObject
from sanket.features import FeatureExtractor, SeatFeatures
from sanket.pose import PoseEstimator, Person
from sanket.render import render_scene, draw_hud
from sanket.report import generate_reports, verify_consistency
from sanket.rules import RuleEngine, RuleFiring
from sanket.scoring import ScoringEngine, Event
from sanket.seats import SeatMap
from sanket.source import open_source, Frame
from sanket.staff import StaffMonitor, StaffEvent
from sanket.store import SessionStore


def main() -> int:
    parser = argparse.ArgumentParser(
        description="SANKET — AI Exam Invigilation Assistant (Store & Reporting)",
    )
    parser.add_argument(
        "positional_source",
        nargs="?",
        default=None,
        help="Path to video file, rtsp/http stream URL, or webcam index ('0')",
    )
    parser.add_argument(
        "--source",
        "-s",
        type=str,
        default=None,
        help="Path to video file, rtsp/http stream URL, or webcam index ('0')",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to YAML configuration file",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Stop processing after N frames",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Display video window with real-time HUD (press 'q' to quit)",
    )
    parser.add_argument(
        "--skeleton-only",
        action="store_true",
        help="Display skeletons on a blank dark background for privacy visualization",
    )
    parser.add_argument(
        "--show-anchors",
        action="store_true",
        default=True,
        help="Render seat anchor bounding boxes",
    )
    parser.add_argument(
        "--show-features",
        action="store_true",
        help="Render live measurement bars next to each seat",
    )
    parser.add_argument(
        "--dump-features",
        action="store_true",
        help="Export all frame feature measurements to runs/features_<ts>.csv",
    )
    parser.add_argument(
        "--no-objects",
        action="store_true",
        help="Disable object detection and authorized object learning",
    )
    parser.add_argument(
        "--seats",
        type=str,
        default=None,
        help="Optional path to manual seats.yaml override",
    )
    parser.add_argument(
        "--disable-rule",
        action="append",
        default=[],
        help="Disable a specific behavioral rule",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Override suspicion alert threshold (default 100)",
    )
    parser.add_argument(
        "--decay",
        type=float,
        default=None,
        help="Override score decay rate in points/sec (default 1.5)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Override model pose weights path",
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=None,
        help="Override model image resolution size",
    )
    parser.add_argument(
        "--frame-skip",
        type=int,
        default=None,
        help="Override frame skip factor",
    )

    args = parser.parse_args()

    source_input = args.source or args.positional_source
    if not source_input:
        parser.error("the following arguments are required: source (or --source)")

    # Load configuration
    try:
        cfg = load_config(args.config)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        return 1

    # Apply CLI overrides
    if args.no_objects:
        cfg.objects["enabled"] = False
    if args.model:
        cfg.model["pose_weights"] = args.model
    if args.imgsz:
        cfg.model["imgsz"] = args.imgsz
    if args.frame_skip:
        cfg.model["frame_skip"] = args.frame_skip
    if args.threshold is not None:
        cfg.scoring["alert_threshold"] = args.threshold
    if args.decay is not None:
        cfg.scoring["decay_rate"] = args.decay
    for disabled in args.disable_rule:
        if disabled in cfg.rules:
            cfg.rules[disabled]["enabled"] = False
            print(f"[RULES] Disabled rule: {disabled}")

    cfg_hash = compute_config_hash(cfg)

    # Ingest video source
    try:
        src = open_source(source_input, config_source=cfg.source)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error initializing source '{source_input}': {e}", file=sys.stderr)
        return 1

    print(f"[SOURCE] Name: {src.name} | Detected FPS: {src.fps:.2f} | Resolution: {src.width}x{src.height} (Scale: {src.scale:.3f})")

    # Initialize Persistence Store
    store = SessionStore()
    session_id = f"sess_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    started_at_iso = datetime.now().isoformat()

    store.create_session({
        "session_id": session_id,
        "source": str(source_input),
        "state": "running",
        "progress": 0.0,
        "frames_processed": 0,
        "frames_total": src.frame_count,
        "duration_s": 0.0,
        "fps_processing": 0.0,
        "seats_tracked": 0,
        "events_total": 0,
        "alerts_total": 0,
        "config_hash": cfg_hash,
        "started_at": started_at_iso,
        "ended_at": None,
        "error_message": None,
    })

    # Initialize Engine Components
    try:
        estimator = PoseEstimator(cfg)
    except Exception as e:
        print(f"Error loading pose estimator: {e}", file=sys.stderr)
        store.update_session(session_id, {"state": "failed", "error_message": str(e)})
        return 1

    seat_map = SeatMap(cfg, manual_seats_path=args.seats)
    feature_extractor = FeatureExtractor(cfg)
    rule_engine = RuleEngine(cfg)
    scoring_engine = ScoringEngine(cfg, session_id=session_id)
    staff_monitor = StaffMonitor(cfg, session_id=session_id)
    calibrators: Dict[str, SeatCalibrator] = {}

    from sanket.hands import MediaPipeHandAnalyzer
    hand_analyzer = MediaPipeHandAnalyzer(cfg) if cfg.get("hands", {}).get("enabled", True) else None

    from sanket.motion import MotionAnalyzer
    motion_analyzer = MotionAnalyzer(cfg) if cfg.get("motion", {}).get("enabled", False) else None

    object_detector = None
    if cfg.objects.get("enabled", True):
        try:
            obj_weights = cfg.objects.get("weights", "models/yolo11m.pt")
            if not Path(obj_weights).is_file() and not Path(obj_weights).exists():
                cfg.objects["weights"] = "yolo11n.pt"
            object_detector = ObjectDetector(cfg)
        except Exception as e:
            print(f"[WARN] Object detector initialization error: {e}")
            object_detector = None

    all_emitted_events: List[Event] = []
    all_staff_events: List[StaffEvent] = []

    frames_processed = 0
    start_wall_time = time.perf_counter()
    last_fps_calc_time = start_wall_time
    last_frame_idx = 0
    current_fps = src.fps
    people_counts: List[int] = []
    unique_raw_track_ids: Set[int] = set()
    last_timeline_sample_t = -999.0
    clip_extractor = ClipExtractor(store=store, clips_dir="clips")
    ring_buffer: deque[tuple[float, np.ndarray]] = deque(maxlen=90)

    try:
        with src:
            for frame in src:
                frames_processed += 1

                # 1. Pose estimation and tracking
                persons = estimator.track(frame)
                people_counts.append(len(persons))
                for p in persons:
                    if p.track_id is not None:
                        unique_raw_track_ids.add(p.track_id)

                # 2. Seat anchoring and staff classification
                seat_assignments, staff_persons = seat_map.update(
                    persons=persons,
                    t=frame.t,
                    frame_shape=frame.image.shape,
                )

                # Ensure calibrators exist
                for sid in seat_map.seats:
                    if sid not in calibrators:
                        calibrators[sid] = SeatCalibrator(sid, cfg)

                # Feed samples to calibrators
                for sid, p in seat_assignments.items():
                    if p is not None and sid in calibrators:
                        seat_obj = seat_map.seats[sid]
                        calibrators[sid].add_sample(
                            person=p,
                            seat=seat_obj,
                            t=frame.t,
                            current_score=seat_obj.score,
                        )
                        seat_obj.calibrated = calibrators[sid].is_calibrated

                # Identify unassigned candidates
                assigned_person_ids = {id(p) for p in seat_assignments.values() if p is not None}
                staff_ids = {id(p) for p in staff_persons}
                unassigned_persons = [
                    p for p in persons if id(p) not in assigned_person_ids and id(p) not in staff_ids
                ]

                # 3. Object Detection & Authorized Object Learning
                detected_objects: List[DetectedObject] = []
                obj_firings: List[RuleFiring] = []
                if object_detector:
                    detected_objects, obj_firings = object_detector.detect_and_evaluate(
                        frame_image=frame.image,
                        frame_index=frame.index,
                        t=frame.t,
                        seat_assignments=seat_assignments,
                        seat_map=seat_map,
                        calibrators=calibrators,
                        unassigned_persons=unassigned_persons,
                    )

                # 4. Geometric Feature Extraction
                seat_features = feature_extractor.extract_features(
                    seat_assignments=seat_assignments,
                    staff_persons=staff_persons,
                    seat_map=seat_map,
                    calibrators=calibrators,
                    t=frame.t,
                )

                # 5. Behavioral Rule Evaluation
                firings_by_seat: Dict[str, List[RuleFiring]] = defaultdict(list)
                for sid, feats in seat_features.items():
                    cal = calibrators.get(sid)
                    is_calibrating = cal is not None and cal.state == CalibrationState.CALIBRATING
                    is_failed = cal is not None and cal.state == CalibrationState.FAILED
                    person = seat_assignments.get(sid)
                    tid = person.track_id if person else None

                    seat_firings = rule_engine.evaluate_seat(
                        features=feats,
                        track_id=tid,
                        frame_index=frame.index,
                        is_calibrating=is_calibrating,
                        is_staff=False,
                        baseline_unavailable=is_failed,
                    )
                    if seat_firings:
                        firings_by_seat[sid].extend(seat_firings)

                # Append object detection firings
                for of in obj_firings:
                    firings_by_seat[of.seat_id].append(of)

                # 4.5 MediaPipe Hand Landmark & Gesture Analysis
                seat_hands = {}
                if hand_analyzer:
                    frame_rgb = cv2.cvtColor(frame.image, cv2.COLOR_BGR2RGB)
                    seat_hands, hand_firings = hand_analyzer.analyze_frame(
                        frame_rgb=frame_rgb,
                        seat_assignments=seat_assignments,
                        t=frame.t,
                        frame_index=frame.index,
                        unassigned_persons=unassigned_persons,
                    )
                    for hf in hand_firings:
                        firings_by_seat[hf.seat_id].append(hf)

                # 4.6 MOG2 & Optical Flow Motion Analysis
                if motion_analyzer:
                    _, motion_firings = motion_analyzer.analyze_frame(
                        frame_bgr=frame.image,
                        seat_map=seat_map,
                        t=frame.t,
                        frame_index=frame.index,
                    )
                    for mf in motion_firings:
                        firings_by_seat[mf.seat_id].append(mf)

                # 6. Suspicion Scoring & Decay
                frame_events = scoring_engine.update(
                    seats=seat_map.seats,
                    firings_by_seat=firings_by_seat,
                    t=frame.t,
                )
                if frame_events:
                    all_emitted_events.extend(frame_events)
                    store.insert_events(frame_events)

                # 6.5 Staff Invigilation Supervision Engine
                staff_events = staff_monitor.update(
                    staff_persons=staff_persons,
                    seat_map=seat_map,
                    student_events=frame_events,
                    t=frame.t,
                    frame_index=frame.index,
                )
                if staff_events:
                    all_staff_events.extend(staff_events)
                    store.insert_staff_events(staff_events)

                # Record periodic timeline samples (every 2.0s)
                if (frame.t - last_timeline_sample_t) >= 2.0:
                    for sid, seat in seat_map.seats.items():
                        store.record_timeline_sample(session_id, sid, frame.t, seat.score)
                    last_timeline_sample_t = frame.t

                # Throughput calculation
                now = time.perf_counter()
                elapsed = now - last_fps_calc_time
                if elapsed >= 0.5:
                    current_fps = (frames_processed - last_frame_idx) / elapsed
                    last_fps_calc_time = now
                    last_frame_idx = frames_processed

                # 7. Render scene
                occupied_seats_count = sum(1 for p in seat_assignments.values() if p is not None)
                calibrated_count = sum(1 for c in calibrators.values() if c.is_calibrated)
                alerts_count = sum(1 for e in all_emitted_events if e.severity == "critical")

                hud_info = {
                    "frame_index": frame.index,
                    "t": frame.t,
                    "fps": current_fps,
                    "source_name": src.name,
                    "device": estimator.device,
                    "frame_skip": estimator.frame_skip,
                    "people_count": len(persons),
                    "seats_tracked": occupied_seats_count,
                    "seats_total": len(seat_map.seats),
                    "calib_count": calibrated_count,
                    "alerts_total": alerts_count,
                    "objects_count": len(detected_objects),
                    "inference_ms": estimator.last_inference_ms,
                }

                annotated = render_scene(
                    frame_image=frame.image,
                    seat_assignments=seat_assignments,
                    staff_persons=staff_persons,
                    unassigned_persons=unassigned_persons,
                    detected_objects=detected_objects,
                    seat_map=seat_map,
                    calibrators=calibrators,
                    seat_features=seat_features,
                    hud_info=hud_info,
                    skeleton_only=args.skeleton_only,
                    show_anchors=args.show_anchors,
                    show_features=args.show_features,
                    seat_hands=seat_hands,
                )

                ring_buffer.append((frame.t, annotated.copy()))

                if frame_events:
                    for evt in frame_events:
                        if evt.severity == "critical":
                            clip_extractor.enqueue_clip(
                                event=evt,
                                ring_buffer=list(ring_buffer),
                                fps=src.fps if src.fps > 0 else 15.0,
                            )

                if args.show:
                    win_title = "SANKET - Exam Invigilation"
                    cv2.imshow(win_title, annotated)
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord("q"):
                        print("[INFO] Processing interrupted by user.")
                        break

                if args.max_frames and frames_processed >= args.max_frames:
                    break

    except KeyboardInterrupt:
        print("\n[INFO] Run interrupted by keyboard.")
    finally:
        clip_extractor.close()
        if args.show:
            cv2.destroyAllWindows()
            cv2.waitKey(1)

    total_wall_time = time.perf_counter() - start_wall_time
    mean_fps = (frames_processed / total_wall_time) if total_wall_time > 0 else 0.0
    source_duration_s = (frames_processed / src.fps) if src.fps > 0 else 0.0

    # Save final seat states to DB
    store.save_seat_states(session_id, seat_map.seats)

    # Save staff states and visits to DB
    store.save_staff_states(session_id, staff_monitor.staff_members)
    all_visits = [v for st in staff_monitor.staff_members.values() for v in st.completed_visits]
    store.save_staff_visits(session_id, all_visits)

    # Save authorized object registry to DB
    if object_detector:
        for sid, reg in object_detector.authorized_registry.items():
            for obj_cls in reg:
                store.record_object_registry(session_id, sid, obj_cls, 0.0, True)

    # Record stream gaps
    for gap_start, gap_end in src.gaps:
        store.record_stream_gap(session_id, gap_start, gap_end)

    # Update session status
    alerts_total = sum(1 for e in all_emitted_events if e.severity == "critical")
    store.update_session(session_id, {
        "state": "done",
        "progress": 1.0,
        "frames_processed": frames_processed,
        "duration_s": round(source_duration_s, 2),
        "fps_processing": round(mean_fps, 1),
        "seats_tracked": len(seat_map.seats),
        "events_total": len(all_emitted_events),
        "alerts_total": alerts_total,
        "ended_at": datetime.now().isoformat(),
    })

    # Generate Reports
    html_path, csv_path = generate_reports(session_id, store, output_dir=cfg.output.get("run_dir", "runs"))

    # Consistency Check
    verify_consistency(session_id, store, html_path, csv_path)

    phone_events = sum(1 for e in all_emitted_events if e.rule in ("object_phone", "hand_phone_grip"))
    zone_str = "Exam Hall (Seated Grid)" if len(seat_map.seats) > 0 else "Reception / Verification Lobby"

    coverage_audit = staff_monitor.generate_coverage_audit(seat_map)

    print("\n" + "=" * 80)
    print("--- SANKET SESSION SUMMARY ---")
    print("=" * 80)
    print(f"Session ID                : {session_id}")
    print(f"Facility Zone             : {zone_str}")
    print(f"Config Hash               : {cfg_hash}")
    print(f"Frames processed          : {frames_processed}")
    print(f"Source duration           : {source_duration_s:.2f}s ({source_duration_s / 60:.2f} min)")
    print(f"Mean processing FPS       : {mean_fps:.1f}")
    print(f"Seats Discovered          : {len(seat_map.seats)}")
    print(f"Seats Calibrated          : {sum(1 for c in calibrators.values() if c.is_calibrated)}")
    print(f"Seats Failed Calib        : {sum(1 for c in calibrators.values() if c.is_failed)}")
    print(f"Unique Persons Tracked    : {len(unique_raw_track_ids)}")
    print(f"Staff Members Monitored   : {len(staff_monitor.staff_members)}")
    print(f"Staff Coverage %          : {coverage_audit['coverage_percentage']:.1f}%")
    print(f"Prohibited Device Events  : {phone_events}")
    print(f"Total Events Generated    : {len(all_emitted_events)}")
    print(f"Critical Alerts (>=100)   : {alerts_total}")
    print(f"Staff Supervision Events  : {len(all_staff_events)}")
    print(f"HTML Report Path          : {html_path}")
    print(f"CSV Report Path           : {csv_path}")
    print("-" * 80)
    print("PER-SEAT SUSPICION SCORES:")
    for sid, seat in sorted(seat_map.seats.items()):
        status_label = "CRITICAL" if seat.peak_score >= cfg.scoring.get("alert_threshold", 100) else "CLEAR"
        print(f"  [{sid}] Final Score: {seat.score:5.1f} | Peak: {seat.peak_score:5.1f} | Status: {status_label}")
    
    if staff_monitor.staff_members:
        print("-" * 80)
        print("STAFF INVIGILATION SUPERVISION & ATTENTION DISTRIBUTION:")
        for st_id, st in sorted(staff_monitor.staff_members.items()):
            med_dwell = st.get_median_dwell()
            print(f"  [{st_id}] Score: {st.score:5.1f} | Peak: {st.peak_score:5.1f} | Median Dwell: {med_dwell:.1f}s | Total Visits: {sum(st.visit_count_per_seat.values())} | Status: {st.status.upper()}")
            for vsid, cnt in sorted(st.visit_count_per_seat.items()):
                dwell = st.dwell_per_seat.get(vsid, 0.0)
                print(f"     -> Visited {vsid}: {cnt} times (total dwell: {dwell:.1f}s)")
    print("=" * 80 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
