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

---

## 6. Long-Session Benchmark (`CAMERA#.mp4` — 100-Minute Exam Session)

- **Source Dataset File**: `DRISHTI AI DEXIT GLobal Datasets/CAMERA#.mp4`
- **Evaluation Artifact**: `runs/long_eval_sess_long_eval_20260822_194916.json`
- **Ground Truth Labels**: `datasets/labels/CAMERA#.json` (11 hand-labelled behavioural events)
- **Session Duration Evaluated**: 100.0 minutes (6,000.0 s | 128,613 frames | 1.67 hours)
- **Processing Throughput**: 29.9 FPS (CPU execution)
- **Seat Mapping**: S1 $\to$ S01 (Center Desk), S3 $\to$ S02 (Top-Right Desk), S4 $\to$ S03 (Bottom-Left Desk)

### Metric Summary:
| Metric | Measurement | Notes / Status |
| :--- | :--- | :--- |
| **Total Labelled Events** | **11** | Full hand-labelled set |
| **Caught Events (Alert $\ge 100$)** | **5** (45.5%) | All 3 sustained phone usage episodes + 2 looking side events caught |
| **Caught Weak (Points Scored)** | **2** (18.2%) | Looking back (13:45) and looking side (20:55) |
| **Near Misses (Tunable)** | **0** (0.0%) | No feature crossed threshold without sufficient duration |
| **Flat Misses (Sub-threshold)** | **4** (36.4%) | 1 standing/leaving (vacating), 1 turn around, 2 sub-2s glances |
| **Structural Misses** | **0** (0.0%) | Calibration completed cleanly for all seats |
| **Seat Rebind Stability** | S01: 15 rebinds, S02: 11 rebinds | Identity anchored to seat; state preserved across all rebinds |
| **Sustained Phone Compounding** | Peak Score: **27,964.4 pts** | Episodes at 1:16, 1:31, 1:35 compound through score accumulation + decay |
| **High-Score Drift Freeze** | **100% Effective** | S02 baseline frozen above score 30; phone posture never absorbed into baseline |
| **Outside-Window Firings** | **781.2 events/hr** | 1,302 events (predominantly S3 continuous talking & reaching towards S1) |

---

## 7. Staff Invigilation Supervision & Attention Distribution Engine

- **Module**: `sanket/staff.py` (`StaffMonitor`)
- **Isolation Invariant**: Staff scores are strictly separated from candidate scores. Staff alerts evaluate supervision quality and coverage, never candidate misconduct.
- **Language Invariant**: 100% compliance with professional supervision vocabulary: *"unusual dwell pattern"*, *"attention distribution"*, *"observed proximity"*, *"supervision review"*.

### Staff Evaluation Benchmark:
| Dataset Clip | Identified Staff | Median Dwell | Desk Visits Recorded | Cumulative Dwell | Max Supervision Score | Status | Rules Fired |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `During the exam...mp4` | `STAFF_06` (Track 6) | $4.2\text{s}$ | 8 visits across 3 desks | $36.0\text{s}$ | $35.0\text{ pts}$ | **NORMAL** | Repeat Visit Observation (4 visits to S02) |
| `06.Candidate...mp4` | `STAFF_01` (Track 1) | $5.5\text{s}$ | 4 visits across 2 desks | $46.6\text{s}$ | $40.0\text{ pts}$ | **NORMAL** | Dwell Pattern (30s at S01, 5.4x median) |
| `05.Crowd observed...mp4` | 18 roving persons | $6.2 - 26.9\text{s}$ | Dispersed open lobby | Variable | $\le 35.0\text{ pts}$ | **NORMAL** | Normal open-floor movement |

### Gate Re-verification:
- **Gate 1 (Hard Negative Empty-Hand)**: **PASS** (0 false student alerts).
- **Gate 2 (CBT Flood Control)**: **PASS** (0 false student alerting seats).
- **Gate 3 (Negative Control Lobby)**: **PASS** (0 alerting candidate seats).
- **Gate 4 (Strongest Alert)**: **PASS** (Immediate phone detection on clips 01, 02, 03).


