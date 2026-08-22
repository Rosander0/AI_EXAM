"""Evaluation of Staff Behavior & Supervision Quality across Dataset Clips."""

import sys
import time
from pathlib import Path
from collections import defaultdict
import numpy as np

from sanket.config import load_config
from sanket.pose import PoseEstimator
from sanket.seats import SeatMap
from sanket.source import open_source
from sanket.staff import StaffMonitor

def evaluate_clip(video_path: str, max_seconds: float = 120.0):
    print(f"\n{'='*75}")
    print(f"EVALUATING STAFF BEHAVIOUR ON: {Path(video_path).name}")
    print(f"{'='*75}")
    
    cfg = load_config("config.yaml")
    cfg.setdefault("model", {})["device"] = "cpu"
    cfg.setdefault("model", {})["frame_skip"] = 3
    
    src = open_source(video_path, cfg)
    estimator = PoseEstimator(cfg)
    seat_map = SeatMap(cfg)
    staff_monitor = StaffMonitor(cfg, session_id=f"eval_staff_{Path(video_path).stem}")
    
    frames_processed = 0
    start_t = time.perf_counter()
    
    with src:
        for frame in src:
            if frame.t > max_seconds:
                break
            frames_processed += 1
            
            persons = estimator.track(frame)
            seat_assignments, staff_persons = seat_map.update(
                persons=persons,
                t=frame.t,
                frame_shape=frame.image.shape,
            )
            
            staff_events = staff_monitor.update(
                staff_persons=staff_persons,
                seat_map=seat_map,
                student_events=[],
                t=frame.t,
                frame_index=frame.index,
            )
            
    wall_t = time.perf_counter() - start_t
    print(f"Processed {frames_processed} frames ({frame.t:.1f}s) in {wall_t:.1f}s ({(frames_processed/wall_t):.1f} FPS)")
    
    audit = staff_monitor.generate_coverage_audit(seat_map)
    print(f"Staff Members Detected   : {len(staff_monitor.staff_members)}")
    print(f"Hall Seats Discovered    : {len(seat_map.seats)}")
    print(f"Hall Coverage Percentage : {audit['coverage_percentage']:.1f}%")
    print(f"Total Staff Rules Fired  : {len(staff_monitor.emitted_events)}")
    
    if staff_monitor.staff_members:
        print("\nPER-STAFF SUPERVISION METRICS:")
        for staff_id, st in staff_monitor.staff_members.items():
            med_dwell = st.get_median_dwell()
            total_visits = sum(st.visit_count_per_seat.values())
            total_dwell = sum(st.dwell_per_seat.values())
            print(f"  * {staff_id} (Track ID {st.track_id}):")
            print(f"      - Supervision Score : {st.score:.1f} (Peak: {st.peak_score:.1f})")
            print(f"      - Status            : {st.status.upper()}")
            print(f"      - Median Dwell      : {med_dwell:.1f}s")
            print(f"      - Total Desk Visits : {total_visits}")
            print(f"      - Cumulative Dwell  : {total_dwell:.1f}s")
            print(f"      - Visited Seats     : {list(st.visit_count_per_seat.keys()) or 'None (Walking Aisle)'}")
            for sid, count in st.visit_count_per_seat.items():
                dwell = st.dwell_per_seat.get(sid, 0.0)
                print(f"          -> {sid}: {count} visits, {dwell:.1f}s dwell")
            if st.last_reason:
                print(f"      - Last Observation  : {st.last_reason}")
    else:
        print("No roving staff identified in this segment (all persons seated candidates or open floor).")

if __name__ == "__main__":
    base = Path("DRISHTI AI DEXIT GLobal Datasets")
    clips = [
        str(base / "During the exam, the candidates exchanged their seats with each other..mp4"),
        str(base / "06.Candidate was found using a mobile phone in the examination hall..mp4"),
        str(base / "05.Crowd observed near the reception and verification desk..mp4"),
    ]
    for c in clips:
        if Path(c).is_file():
            evaluate_clip(c, max_seconds=60.0)
