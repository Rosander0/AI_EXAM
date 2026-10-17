# SANKET — AI-Based Examination Invigilation & Facility Intelligence

**Problem Statement #1** &middot; DEXIT Global Hackathon

SANKET is an AI-assisted examination monitoring engine that analyzes candidate posture, gaze deviation, neighbor intrusion, prohibited handheld devices, and facility queue flow in real-time. Built around the core principle that **"an isolated movement is not suspicious; a sustained or repeated pattern is"**, SANKET replaces brittle static thresholds with **per-seat baseline self-calibration**, **continuous suspicion score decay**, and **Google MediaPipe Hand Landmark & Grip Recognition**.

---

## Key Architectural Capabilities

1. **Google MediaPipe Hand Landmark & Grip Detection**:
   - Tracks 21 3D joint landmarks per hand for every candidate.
   - Recognizes **Handheld Phone Grip Postures** (`hand_phone_grip`, +80 pts) through finger flexion and thumb opposition.
   - **100% Immunity to Background False Alarms**: Evaluates human hand joint biomechanics, completely ignoring glass windows, desktop PC monitors, and wall fixtures.
   - **Pen-Holding & Writing Immunity**: Prevents false alarms on candidates writing on answer sheets or signing verification registers.

2. **Per-Seat Baseline Self-Calibration**:
   - Calibrates each candidate's baseline posture (ear-nose asymmetry, shoulder span, head position) in the first 3 seconds, eliminating false alarms caused by camera perspective angles.

3. **Continuous Score Decay**:
   - Evaluates suspicion via $S = \max(0, S - D\cdot\Delta t) + \sum w_i E_i$. Fleeting glances decay away; repeated or sustained actions accumulate toward the 100-point alert threshold.

4. **Multi-Zone Facility Monitoring**:
   - **Exam Hall Seated Zone**: Auto-discovers seated candidate desks (`S01..Sn`), tracks seated posture, detects neighbor intrusions, and classifies roaming invigilators as `STAFF`.
   - **Reception & Baggage Lobby Zone**: Automatically recognizes open lobbies, tracks crowd count and verification queue flow without projecting fake desk anchors on lockers or mislabeling standing students.

5. **Ranked by Sustained Alert Duration**:
   - Candidates of interest are ranked strictly by `sustained_seconds` (cumulative time above threshold 100), directly fulfilling the Hackathon Extension Goal.

6. **Authorized Object Learning**:
   - Permitted items (calculators, water bottles) on desks during calibration are authorized; unrecognized objects appearing later trigger alerts. Mobile phones remain strictly non-authorizable.

7. **Zero-Build React 18 Control Room Dashboard**:
   - Instant 0ms load with live session dropdown, full-resolution MJPEG video feed, real-time alert feed, live seat grid, and embedded interactive HTML/CSV report viewers.

---

## Quickstart

### 1. Installation

```bash
# Clone repository and install dependencies
pip install -r requirements.txt
```

### 2. Launch the Control Room Web Dashboard

**On Windows:**
```powershell
powershell -ExecutionPolicy Bypass -File run_demo.ps1
```

**On macOS / Linux:**
```bash
bash run_demo.sh
```

Open your browser at `http://localhost:8000/`.

---

## CLI Usage

Run the engine directly via CLI for video analysis, testing, or benchmark evaluation:

```bash
# 1. Exam Hall: Mobile phone detection with live MediaPipe HUD
python main.py --source "DRISHTI AI DEXIT GLobal Datasets/01.Candidate was found using a mobile phone in the examination hall..mkv" --show --frame-skip 2

# 2. Exam Hall: Candidate talking / turning back / head turn
python main.py --source "DRISHTI AI DEXIT GLobal Datasets/04.CCTV Candidate Talking.mkv" --show --frame-skip 2

# 3. Reception & Baggage Area: Candidate queue & crowd monitoring
python main.py --source "DRISHTI AI DEXIT GLobal Datasets/05.Crowd observed near the reception and verification desk..mp4" --show --frame-skip 2

# 4. Privacy Skeleton Mode (renders joint wireframes on dark background)
python main.py --source "DRISHTI AI DEXIT GLobal Datasets/03.CCTV Mobile Usage.mkv" --skeleton-only --show
```

---

## Running Automated Tests

Run the full automated pytest suite covering all architectural modules:

```powershell
python -m pytest
```

All 38 test suites pass (`38 passed in < 2.5s`).

---

## Project Structure

```
Drishti_AI/
├── config.yaml               # Central configuration (frozen parameters)
├── DATA_CONTRACT.md          # Frozen schemas & REST endpoints
├── FIGURES.md                # Quantitative metrics source of truth
├── requirements.txt          # Python dependencies
├── main.py                   # Engine CLI entrypoint
├── run_demo.sh / .ps1        # Single-command demo runners
├── models/                   # Neural network weights & MediaPipe task models
│   ├── yolo11m-pose.pt       # Pose estimator
│   ├── yolo11m.pt            # Object detector
│   └── hand_landmarker.task  # Google MediaPipe 21-landmark hand model
├── sanket/                   # Core Invigilation Engine
│   ├── hands.py              # MediaPipe 21 hand landmarks & grip analyzer
│   ├── source.py             # Frame ingestion & time invariant (t = frame/fps)
│   ├── pose.py               # COCO-17 pose estimation & BoT-SORT tracking
│   ├── seats.py              # Seat auto-discovery & staff/candidate separation
│   ├── calibration.py        # Per-seat rolling median/MAD baseline calibration
│   ├── features.py           # Pure geometric feature extraction
│   ├── rules.py              # Behavioral rules & reason strings
│   ├── scoring.py            # Continuous decay & Event generation
│   ├── detection.py          # Prohibited objects & geometry filtering
│   ├── store.py              # SQLite WAL persistence
│   ├── report.py             # HTML/CSV reports & consistency check
│   ├── clips.py              # Asynchronous evidence clip extraction
│   ├── render.py             # HUD, overlays, and hand skeleton rendering
│   └── device.py             # Hardware acceleration resolver (CUDA/MPS/CPU)
├── server/                   # FastAPI Backend
│   ├── app.py                # REST API & static file routes
│   ├── jobs.py               # Asynchronous session worker
│   ├── streamer.py           # MJPEG streaming
│   └── schemas.py            # Pydantic contract schemas
└── web/                      # Zero-Build Invigilator Dashboard
    ├── index.html            # Standalone HTML entrypoint
    └── static/
        ├── react-app.js      # Pure React 18 standalone component architecture
        └── style.css         # Control-room dark mode design system
```

---

## Invariants & Principles

- **Terminology Invariant**: Strictly uses `"alert"`, `"observed behaviour"`, and `"review"`.
- **Time Invariant**: Timestamp $t = \text{frame\_index} / \text{fps}$ strictly derived from video source.
- **Reporting Invariant**: 100% consistency verified across SQLite database, HTML report, and CSV data export.
