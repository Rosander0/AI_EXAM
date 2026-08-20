"""Video input abstraction for SANKET.

CRITICAL INVARIANT:
Time (t) comes strictly from the source:
  t = frame_index / fps for recorded sources.
NEVER use wall-clock time for t on recorded video. All downstream behavioral
rule durations, score accumulation, and decay depend on this invariance.
For live sources (RTSP, webcam), t is the elapsed wall-clock time since ingestion started.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import time
from typing import Iterator, List, Optional, Tuple
import cv2
import numpy as np


@dataclass
class Frame:
    """Represents a single video frame with source-derived metadata."""
    index: int
    t: float
    image: np.ndarray


class FrameSource:
    """Universal frame source context manager for files, streams, and webcams."""

    def __init__(self, spec: str | int, config_source: Optional[dict] = None):
        self.spec = spec
        self.config = config_source or {}
        self.fps_override = self.config.get("fps_override")
        self.resize_width = self.config.get("resize_width", 1280)
        self.reconnect_max_seconds = self.config.get("reconnect_max_seconds", 30)
        self.rtsp_buffer_size = self.config.get("rtsp_buffer_size", 1)

        self.cap: Optional[cv2.VideoCapture] = None
        self.is_live: bool = False
        self.name: str = ""
        self.fps: float = 30.0
        self.orig_width: int = 0
        self.orig_height: int = 0
        self.width: int = 0
        self.height: int = 0
        self.scale: float = 1.0  # Scale factor = resized_dimension / original_dimension
        self.frame_count: Optional[int] = None
        self.gaps: List[Tuple[float, float]] = []

        self._start_wall_time: Optional[float] = None
        self._classify_and_init()

    def _classify_and_init(self) -> None:
        """Classifies the source spec and verifies initial accessibility."""
        spec_str = str(self.spec).strip()

        # 1. Webcam spec (e.g., "0", 0, "1")
        if isinstance(self.spec, int) or spec_str.isdigit():
            self.source_target = int(self.spec)
            self.is_live = True
            self.name = f"Webcam_{self.source_target}"
        # 2. Network Stream (RTSP / HTTP)
        elif spec_str.lower().startswith(("rtsp://", "http://", "https://")):
            self.source_target = spec_str
            self.is_live = True
            self.name = spec_str.split("?")[0]
        # 3. Local Video File
        else:
            file_path = Path(spec_str)
            if not file_path.is_file():
                raise FileNotFoundError(f"Source video file not found: {spec_str}")
            self.source_target = str(file_path)
            self.is_live = False
            self.name = file_path.name

        self._open_capture()

    def _open_capture(self) -> None:
        """Opens the OpenCV VideoCapture and initializes dimensions/FPS."""
        if self.cap is not None:
            self.cap.release()

        self.cap = cv2.VideoCapture(self.source_target)
        if not self.cap.isOpened():
            raise RuntimeError(f"Failed to open video source: {self.spec}")

        # If RTSP/live, set buffer size to avoid frame queuing delay
        if self.is_live and hasattr(cv2, "CAP_PROP_BUFFERSIZE"):
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, self.rtsp_buffer_size)

        # Retrieve properties
        raw_fps = self.cap.get(cv2.CAP_PROP_FPS)
        if self.fps_override is not None and self.fps_override > 0:
            self.fps = float(self.fps_override)
        elif raw_fps and raw_fps > 0:
            self.fps = float(raw_fps)
        else:
            self.fps = 30.0

        self.orig_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1280
        self.orig_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720

        if not self.is_live:
            total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.frame_count = total_frames if total_frames > 0 else None
        else:
            self.frame_count = None

        # Compute resize scale (treating resize_width as a CAP; never upscaling)
        if self.resize_width and self.orig_width > self.resize_width:
            self.scale = self.resize_width / float(self.orig_width)
            self.width = int(self.resize_width)
            self.height = int(round(self.orig_height * self.scale))
        else:
            self.scale = 1.0
            self.width = self.orig_width
            self.height = self.orig_height

    def __enter__(self) -> FrameSource:
        self._start_wall_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def close(self) -> None:
        """Releases the video capture resource cleanly."""
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def __iter__(self) -> Iterator[Frame]:
        """Iterates through frames, computing source timestamps and handling stream drops."""
        frame_idx = 0
        reconnect_backoff = 0.5

        if self._start_wall_time is None:
            self._start_wall_time = time.time()

        while True:
            if self.cap is None or not self.cap.isOpened():
                if not self.is_live:
                    break
                # Live stream reconnection with backoff
                gap_start = time.time() - self._start_wall_time
                reconnected = False
                backoff = reconnect_backoff
                while (time.time() - self._start_wall_time - gap_start) < self.reconnect_max_seconds:
                    time.sleep(backoff)
                    try:
                        self._open_capture()
                        if self.cap.isOpened():
                            reconnected = True
                            gap_end = time.time() - self._start_wall_time
                            self.gaps.append((gap_start, gap_end))
                            break
                    except Exception:
                        pass
                    backoff = min(backoff * 2.0, 5.0)

                if not reconnected:
                    break

            ret, raw_frame = self.cap.read()
            if not ret:
                if self.is_live:
                    gap_start = time.time() - self._start_wall_time
                    self.cap.release()
                    continue
                else:
                    # End of recorded video
                    break

            # Invariant: Calculate source timestamp t
            # For recorded video: t = frame_index / fps (exact deterministic source time)
            # For live streams: t = elapsed wall-clock seconds since capture started
            if self.is_live:
                t = time.time() - self._start_wall_time
            else:
                t = frame_idx / self.fps

            # Scale down if width exceeds resize_width cap
            if self.scale != 1.0:
                frame_img = cv2.resize(
                    raw_frame,
                    (self.width, self.height),
                    interpolation=cv2.INTER_AREA,
                )
            else:
                frame_img = raw_frame

            yield Frame(index=frame_idx, t=t, image=frame_img)
            frame_idx += 1


def open_source(spec: str | int, config_source: Optional[dict] = None) -> FrameSource:
    """Factory helper returning a configured FrameSource context manager."""
    return FrameSource(spec=spec, config_source=config_source)
