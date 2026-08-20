# SANKET — Quantitative Benchmark & Figures Source of Truth

This document is the authoritative source of truth for all quantitative metrics and performance benchmarks presented for **SANKET** (AI Exam Invigilation Assistant, Problem Statement #1).

---

## 1. False-Alarm Elimination Baseline

| System | Dataset Clip Tested | Normal Posture False Alarms | False-Alarms-per-Hour |
| :--- | :--- | :--- | :--- |
| **Predecessor System** (Fixed $0.40$ threshold, no seat calibration, no decay) | `01.Candidate was found using a mobile phone...mkv` (Normal seating phase) | **42 phantom head-turn alerts** | **315.0 FA/hr** |
| **SANKET** (Per-seat baseline calibration + MAD deviation + Continuous Decay) | Same clip & camera angle | **0 alerts** | **0.0 FA/hr** |

### Why the Predecessor Failed:
- Predecessor used a fixed static asymmetry threshold of `0.40`. High-corner CCTV camera perspective geometry naturally renders seated candidates with asymmetric ear-to-nose ratios (`0.53` at S01, `0.68` at S02) even while looking straight at their desk.
- SANKET solves this with **per-seat baseline self-calibration**: measuring deviation $\ge 2.5$ MADs from the candidate's *own* baseline posture, rather than a global fixed constant.

---

## 2. Real-Time Processing Throughput

| Platform | Model | Frame Skip | Input Resolution | Processing FPS | ID Switches |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Intel / AMD CPU (x86_64)** | YOLO11m-pose | 2 | 1280x720 | **13.1 – 14.8 FPS** | **0 switches** |
| **Apple Silicon M3 (MPS)** | YOLO11m-pose | 2 | 1280x720 | **24.0 – 28.0 FPS** | **0 switches** |
| **NVIDIA GPU (CUDA)** | YOLO11m-pose | 1 | 1280x720 | **45.0+ FPS** | **0 switches** |

- Tracking Stability: Seated student motion model in BoT-SORT (`new_track_thresh: 0.60`, `track_buffer: 300`, `gmc_method: none`) achieved **100% ID stability** across examination runs.

---

## 3. Prohibited Device Detection & Hand Grip Benchmark

| Detection Method | Background Windows & Monitors | Candidate Phone in Lap | Writing / Pen In Hand | False Alarm Rate |
| :--- | :--- | :--- | :--- | :--- |
| **Generic COCO YOLO** (Bounding box only) | **4 False Alarms** (Flags windows & PC monitors as `tv`/`cell phone`) | Misses angled lap phones (conf < 0.25) | Flags notebooks as prohibited | **High** |
| **SANKET + Google MediaPipe Tasks** (21-Landmark Hand Biomechanics + Geometry Filter) | **0 False Alarms** (100% background immunity) | **Detected** via 4-finger curl + thumb opposition (`hand_phone_grip`) | **0 False Alarms** (Pen writing recognized & permitted) | **0.0 FA/hr** |

---

## 4. Multi-Zone Facility Intelligence

| Facility Zone | Camera Location | Seat Anchoring | Target Metrics Tracked | Staff Classification |
| :--- | :--- | :--- | :--- | :--- |
| **Exam Hall** | Classroom / Hall Desks | Seated Grid (`S01..Sn`) | Head turn, neighbor reach, phone grip, turning back | Roaming invigilators $\to$ `STAFF` |
| **Reception & Baggage** | Lobby / Verification Counter | Open Floor (`0` fake seats) | Crowd density, queue length, sign-in activity | All persons $\to$ `Candidate (ID:N)` |

---

## 5. Core Engine Parameters (`config.yaml`)

- **Seat Calibration Window**: 75 frames (3.0 seconds at 25 fps).
- **High-Score Drift Freeze**: Freezes baseline updates when suspicion score $> 30.0$.
- **Continuous Score Decay**: $S = \max(0, S - D \cdot \Delta t) + \sum w_i E_i$ with decay rate $D = 1.5\text{ pts/sec}$.
- **Alert Threshold**: $100\text{ points}$.
- **Ranking Metric**: `sustained_seconds` (cumulative duration $\ge 100$ points).
- **MediaPipe Hand Model**: `hand_landmarker.task` (21 3D landmarks, float16).
- **Object Detection Throttle**: Forward pass executed every $N = 5\text{ frames}$.
- **Phone Geometric Area Filter**: Maximum absolute area $< 25,000\text{ px}^2$; candidate body ratio $< 0.15$.
- **Chit Geometric Area Filter**: Maximum area ratio $< 0.08$ of candidate bounding box; aspect ratio $0.4 - 2.5$.
