from sanket.config import load_config
from sanket.pose import PoseEstimator
from sanket.seats import SeatMap
from sanket.calibration import SeatCalibrator
from sanket.source import open_source

cfg = load_config()
cfg.identity["discovery_seconds"] = 0.5
cfg.calibration["min_samples"] = 20
cfg.calibration["seconds"] = 1.0
cfg.model["frame_skip"] = 2

estimator = PoseEstimator(cfg)
seat_map = SeatMap(cfg)
calibrators = {}

src = open_source("DRISHTI AI DEXIT GLobal Datasets/01.Candidate was found using a mobile phone in the examination hall..mkv")

frames_run = 0
with src:
    for frame in src:
        frames_run += 1
        persons = estimator.track(frame)
        assigns, staff = seat_map.update(persons, frame.t, frame.image.shape)

        for sid, p in assigns.items():
            if sid not in calibrators:
                calibrators[sid] = SeatCalibrator(sid, cfg)
            if p is not None:
                calibrators[sid].add_sample(p, seat_map.seats[sid], frame.t)

        if frames_run >= 80:
            break

print("=== CALIBRATION RESULTS ON REAL FOOTAGE ===")
for sid, c in calibrators.items():
    print(f"Seat {sid}: State={c.state.value}, Samples={c.sample_count}, Baseline Asymmetry={c.baseline('ear_nose_asymmetry'):.3f}, Spread={c.spread('ear_nose_asymmetry'):.3f}, Baseline Span={c.baseline('shoulder_span'):.1f}px")
