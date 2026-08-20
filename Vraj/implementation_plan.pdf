# Implementation Plan: SANKET — Foundation & Test Version (Prompt 1)

Building **SANKET** (AI Exam Invigilation Assistant) according to the handoff specification for Problem Statement #1 (*AI-Based Human Behaviour Monitoring Using Pose Estimation and Gesture Analysis*).

Following the handoff discipline: **Go step-by-step, never build two prompts before testing one, and do not over-extend.**

---

## Architecture & System Invariants

1. **Time Base Invariant**: All timestamps and durations derive strictly from the source (\(t = \text{frame\_index} / \text{fps}\)), never wall-clock time for recorded media.
2. **Data Contract**: Standard schema for Events, Seat States, Sessions, and API endpoints saved in `DATA_CONTRACT.md`.
3. **Hardware & Environment**: CPU / MPS device resolution with graceful fallback.
4. **Clean Code & Separation**:
   - `config.yaml` manages all thresholds and settings.
   - `sanket/render.py` is the only module responsible for drawing on frames.
   - `sanket/source.py` abstracts video files, RTSP/HTTP streams, and webcams uniformly.
5. **Ethical & Terminology Standard**: Strictly use the vocabulary *alert, observed behaviour, review*. The word "cheating" is never used.

---

## User Review Required

> [!IMPORTANT]
> - This plan initiates **Prompt 1 (Foundation and Video Input)** of the 12-prompt handoff roadmap.
> - No pose estimation or tracking is loaded in this prompt; the goal is rock-solid video ingestion, timestamping, CLI harness, config parsing, and HUD rendering.
> - Once verified, we will systematically proceed to Prompt 2 (Pose Estimation & Tracking), Prompt 3 (Seat Anchoring), etc.

---

## Proposed Changes (Prompt 1: Foundation & Video Input)

### Root Configuration & Documentation

#### [NEW] [DATA_CONTRACT.md](file:///c:/Users/Vraj/Documents/Drishti_AI/DATA_CONTRACT.md)
- Define the frozen schemas: Event, Seat state, Session state, and API endpoints as mandated by Part B of the handoff.

#### [NEW] [config.yaml](file:///c:/Users/Vraj/Documents/Drishti_AI/config.yaml)
- Define complete configuration structure:
  - `source`: `fps_override`, `resize_width` (1280), `reconnect_max_seconds` (30), `rtsp_buffer_size` (1)
  - `model`: `pose_weights`, `imgsz` (640), `conf` (0.25), `keypoint_min_conf` (0.5), `device` (auto), `half` (false), `frame_skip` (1)
  - `identity`, `calibration`, `rules`, `objects`, `scoring`, `output` placeholders with default parameters.

#### [NEW] [requirements.txt](file:///c:/Users/Vraj/Documents/Drishti_AI/requirements.txt)
- Pin core dependencies: `opencv-python`, `numpy`, `pyyaml`, `ultralytics`, `torch`, `fastapi`, `uvicorn`, `pydantic`.

---

### Core Package (`sanket/`)

#### [NEW] [sanket/\_\_init\_\_.py](file:///c:/Users/Vraj/Documents/Drishti_AI/sanket/__init__.py)
- Package initialization and version definition.

#### [NEW] [sanket/log.py](file:///c:/Users/Vraj/Documents/Drishti_AI/sanket/log.py)
- Structured logging utility.

#### [NEW] [sanket/config.py](file:///c:/Users/Vraj/Documents/Drishti_AI/sanket/config.py)
- Config loader and validator with dictionary attribute access and defaults fallback.

#### [NEW] [sanket/device.py](file:///c:/Users/Vraj/Documents/Drishti_AI/sanket/device.py)
- `resolve_device(pref)` returning `"mps"` or `"cpu"`.
- Sets `PYTORCH_ENABLE_MPS_FALLBACK=1` on import.

#### [NEW] [sanket/source.py](file:///c:/Users/Vraj/Documents/Drishti_AI/sanket/source.py)
- `Frame` dataclass (`index: int`, `t: float`, `image: np.ndarray`).
- `FrameSource` context manager handling file paths, RTSP/HTTP URLs, webcam index integers.
- Calculates \(t = \text{index} / \text{fps}\) for recorded video and wall-clock elapsed for live streams.
- Aspect ratio preserving downscale to `resize_width` as a ceiling cap (never upscaling), exposing `.scale`.
- Gap tracking for stream drops (`.gaps` list).

#### [NEW] [sanket/render.py](file:///c:/Users/Vraj/Documents/Drishti_AI/sanket/render.py)
- HUD drawing function: `draw_hud(frame, info: dict)` placing compact, jitter-free fixed-width top-left overlay (Frame index, Timestamp `MM:SS.mmm`, FPS, source name).

---

### Main Entrypoint

#### [NEW] [main.py](file:///c:/Users/Vraj/Documents/Drishti_AI/main.py)
- CLI entrypoint: `python main.py --source <spec> [--show] [--max-frames N] [--config path]`.
- Iterates frames, renders HUD, optionally displays video preview with 'q' to exit.
- Summarizes frames processed, source duration, wall time, mean FPS, and detected gaps.

---

## Verification Plan

### Automated & CLI Verification
1. **File Source Test**:
   ```bash
   python main.py --source "DRISHTI AI DEXIT GLobal Datasets/01.Candidate was found using a mobile phone in the examination hall..mkv" --max-frames 100
   ```
   *Expectation*: Processes exactly 100 frames, prints resolved device, source FPS, wall time, mean processing FPS, clean summary.
2. **Error Handling Test**:
   ```bash
   python main.py --source "nonexistent_video.mp4"
   ```
   *Expectation*: Clean one-line error message without a traceback.
3. **Time Base Verification**:
   Verify calculated frame timestamps ($t$) accurately match $\text{index} / \text{fps}$ and duration.
