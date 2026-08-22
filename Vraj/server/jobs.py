"""Session Job Runner for SANKET.

CRITICAL DESIGN PRINCIPLE:
The runner WRAPS our existing engine pipeline in a background thread.
It does NOT reimplement detection, rules, or scoring.
Robustness: If the engine thread crashes, the session goes to state 'failed'
with error stored, and the FastAPI server keeps serving.
"""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
import threading
import time
import traceback
from typing import Any, Dict, List, Optional, Set
import cv2
import numpy as np

from sanket.calibration import CalibrationState, SeatCalibrator
from sanket.clips import ClipExtractor
from sanket.config import compute_config_hash, load_config
from sanket.detection import ObjectDetector, DetectedObject
from sanket.features import FeatureExtractor, SeatFeatures
from sanket.pose import PoseEstimator, Person
from sanket.render import render_scene
from sanket.report import generate_reports, verify_consistency
from sanket.rules import RuleEngine, RuleFiring
from sanket.scoring import ScoringEngine, Event
from sanket.seats import SeatMap
from sanket.source import open_source
from sanket.store import SessionStore
from server.streamer import streamer


class JobRunner:
    """Manages asynchronous engine sessions and status polling."""

    def __init__(self, store: SessionStore):
        self.store = store
        self.active_session_id: Optional[str] = None
        self.active_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._stop_requested = threading.Event()

    def is_busy(self) -> bool:
        with self._lock:
            return self.active_thread is not None and self.active_thread.is_alive()

    def start_session(self, source_path: str, config_overrides: Optional[dict] = None) -> Dict[str, Any]:
        """Starts an engine run in a background worker thread."""
        with self._lock:
            if self.active_thread is not None and self.active_thread.is_alive():
                self._stop_requested.set()
                self.active_thread.join(timeout=1.5)
                self.active_thread = None

            self._stop_requested.clear()
            session_id = f"sess_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.active_session_id = session_id

            # Load configuration
            cfg = load_config(overrides=config_overrides)
            cfg_hash = compute_config_hash(cfg)

            # Register session in database
            session_record = {
                "session_id": session_id,
                "source": str(source_path),
                "state": "running",
                "progress": 0.0,
                "frames_processed": 0,
                "frames_total": None,
                "duration_s": 0.0,
                "fps_processing": 0.0,
                "seats_tracked": 0,
                "events_total": 0,
                "alerts_total": 0,
                "config_hash": cfg_hash,
                "started_at": datetime.now().isoformat(),
                "ended_at": None,
                "error_message": None,
            }
            self.store.create_session(session_record)

            self.active_thread = threading.Thread(
                target=self._run_pipeline,
                args=(session_id, source_path, cfg),
                daemon=True,
            )
            self.active_thread.start()

            return session_record

    def stop_session(self) -> None:
        """Signals the background worker to stop gracefully."""
        self._stop_requested.set()

    def _run_pipeline(self, session_id: str, source_spec: str, cfg: Any) -> None:
        """Worker thread executing the full SANKET pipeline."""
        try:
            # 1. Ingest source
            src = open_source(source_spec, config_source=cfg.get("source", {}))
            self.store.update_session(session_id, {"frames_total": src.frame_count})

            # 2. Instantiate pipeline components
            estimator = PoseEstimator(cfg)
            seat_map = SeatMap(cfg)
            feature_extractor = FeatureExtractor(cfg)
            rule_engine = RuleEngine(cfg)
            scoring_engine = ScoringEngine(cfg, session_id=session_id)
            calibrators: Dict[str, SeatCalibrator] = {}

            from sanket.hands import MediaPipeHandAnalyzer
            hand_analyzer = MediaPipeHandAnalyzer(cfg) if cfg.get("hands", {}).get("enabled", True) else None

            object_detector = None
            if cfg.get("objects", {}).get("enabled", True):
                try:
                    obj_weights = cfg.objects.get("weights", "models/yolo11m.pt")
                    if not Path(obj_weights).is_file() and not Path(obj_weights).exists():
                        cfg.objects["weights"] = "yolo11n.pt"
                    object_detector = ObjectDetector(cfg)
                except Exception:
                    object_detector = None

            all_emitted_events: List[Event] = []
            frames_processed = 0
            start_wall_time = time.perf_counter()
            last_fps_calc_time = start_wall_time
            last_progress_update_time = start_wall_time
            last_frame_idx = 0
            current_fps = src.fps
            last_timeline_sample_t = -999.0

            clip_extractor = ClipExtractor(store=self.store, clips_dir="clips")
            ring_buffer: deque[tuple[float, np.ndarray]] = deque(maxlen=90)

            with src:
                for frame in src:
                    if self._stop_requested.is_set():
                        break

                    frames_processed += 1

                    # A. Pose Estimation & Tracking
                    persons = estimator.track(frame)

                    # B. Seat Anchoring & Staff Classification
                    seat_assignments, staff_persons = seat_map.update(
                        persons=persons,
                        t=frame.t,
                        frame_shape=frame.image.shape,
                    )

                    # Ensure calibrators
                    for sid in seat_map.seats:
                        if sid not in calibrators:
                            calibrators[sid] = SeatCalibrator(sid, cfg)

                    for sid, p in seat_assignments.items():
                        if p is not None and sid in calibrators:
                            seat_obj = seat_map.seats[sid]
                            calibrators[sid].add_sample(p, seat_obj, frame.t, current_score=seat_obj.score)
                            seat_obj.calibrated = calibrators[sid].is_calibrated

                    # Identify unassigned candidates
                    assigned_pids = {id(p) for p in seat_assignments.values() if p is not None}
                    staff_pids = {id(p) for p in staff_persons}
                    unassigned_persons = [
                        p for p in persons if id(p) not in assigned_pids and id(p) not in staff_pids
                    ]

                    # C. Object Detection
                    detected_objs: List[DetectedObject] = []
                    obj_firings: List[RuleFiring] = []
                    if object_detector:
                        detected_objs, obj_firings = object_detector.detect_and_evaluate(
                            frame_image=frame.image,
                            frame_index=frame.index,
                            t=frame.t,
                            seat_assignments=seat_assignments,
                            seat_map=seat_map,
                            calibrators=calibrators,
                            unassigned_persons=unassigned_persons,
                        )

                    # D. Feature Extraction
                    seat_features = feature_extractor.extract_features(
                        seat_assignments=seat_assignments,
                        staff_persons=staff_persons,
                        seat_map=seat_map,
                        calibrators=calibrators,
                        t=frame.t,
                    )

                    # E. Rule Evaluation
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

                    for of in obj_firings:
                        firings_by_seat[of.seat_id].append(of)

                    # E.5 MediaPipe Hands
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

                    # F. Scoring & Decay
                    frame_events = scoring_engine.update(
                        seats=seat_map.seats,
                        firings_by_seat=firings_by_seat,
                        t=frame.t,
                    )
                    if frame_events:
                        all_emitted_events.extend(frame_events)
                        self.store.insert_events(frame_events)

                    # Progress & Periodic timeline samples
                    if (frame.t - last_timeline_sample_t) >= 2.0:
                        for sid, seat in seat_map.seats.items():
                            self.store.record_timeline_sample(session_id, sid, frame.t, seat.score)
                        last_timeline_sample_t = frame.t

                    # Update progress every ~0.5s wall time
                    now = time.perf_counter()
                    if (now - last_progress_update_time) >= 0.5:
                        progress = (frames_processed / src.frame_count) if (src.frame_count and src.frame_count > 0) else 0.0
                        elapsed = now - last_fps_calc_time
                        if elapsed > 0:
                            current_fps = (frames_processed - last_frame_idx) / elapsed
                            last_fps_calc_time = now
                            last_frame_idx = frames_processed

                        occupied_seats_count = sum(1 for p in seat_assignments.values() if p is not None)
                        alerts_count = sum(1 for e in all_emitted_events if e.severity == "critical")
                        source_dur = (frames_processed / src.fps) if src.fps > 0 else 0.0

                        self.store.update_session(session_id, {
                            "progress": min(0.99, progress),
                            "frames_processed": frames_processed,
                            "duration_s": round(source_dur, 2),
                            "fps_processing": round(current_fps, 1),
                            "seats_tracked": len(seat_map.seats),
                            "events_total": len(all_emitted_events),
                            "alerts_total": alerts_count,
                        })
                        last_progress_update_time = now

                    # G. Render Scene & Stream
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
                        "objects_count": len(detected_objs),
                        "inference_ms": estimator.last_inference_ms,
                    }

                    annotated = render_scene(
                        frame_image=frame.image,
                        seat_assignments=seat_assignments,
                        staff_persons=staff_persons,
                        unassigned_persons=unassigned_persons,
                        detected_objects=detected_objs,
                        seat_map=seat_map,
                        calibrators=calibrators,
                        seat_features=seat_features,
                        hud_info=hud_info,
                        skeleton_only=False,
                        show_anchors=True,
                        show_features=True,
                        seat_hands=seat_hands,
                    )

                    streamer.update_frame(session_id, annotated)

                    # H. Buffer annotated frame and extract evidence video clips for critical events
                    ring_buffer.append((frame.t, annotated.copy()))

                    if frame_events:
                        for evt in frame_events:
                            if evt.severity == "critical":
                                # Extract video clip
                                clip_extractor.enqueue_clip(
                                    event=evt,
                                    ring_buffer=list(ring_buffer),
                                    fps=src.fps if src.fps > 0 else 15.0,
                                )

            # Finalize Session
            total_wall_time = time.perf_counter() - start_wall_time
            mean_fps = (frames_processed / total_wall_time) if total_wall_time > 0 else 0.0
            source_dur = (frames_processed / src.fps) if src.fps > 0 else 0.0

            self.store.save_seat_states(session_id, seat_map.seats)
            alerts_total = sum(1 for e in all_emitted_events if e.severity == "critical")
            self.store.update_session(session_id, {
                "state": "done",
                "progress": 1.0,
                "frames_processed": frames_processed,
                "duration_s": round(source_dur, 2),
                "fps_processing": round(mean_fps, 1),
                "seats_tracked": len(seat_map.seats),
                "events_total": len(all_emitted_events),
                "alerts_total": alerts_total,
                "ended_at": datetime.now().isoformat(),
            })

            # Generate Reports
            html_p, csv_p = generate_reports(session_id, self.store, output_dir=cfg.get("output", {}).get("run_dir", "runs"))
            verify_consistency(session_id, self.store, html_p, csv_p)

        except Exception as e:
            err_msg = f"{type(e).__name__}: {str(e)}"
            traceback.print_exc()
            self.store.update_session(session_id, {
                "state": "failed",
                "error_message": err_msg,
                "ended_at": datetime.now().isoformat(),
            })
        finally:
            streamer.set_idle()
            with self._lock:
                self.active_session_id = None
