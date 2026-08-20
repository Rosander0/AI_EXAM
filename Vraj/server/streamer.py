"""MJPEG Video Streamer for SANKET.

Serves real-time annotated frame streams over HTTP.
When idle or session disconnected, serves a static dark control frame rather than hanging.
"""

from __future__ import annotations

import threading
import time
from typing import Iterator, Optional
import cv2
import numpy as np


class FrameStreamer:
    """Thread-safe frame buffer and MJPEG generator."""

    def __init__(self, fps: int = 10, quality: int = 70):
        self.fps = fps
        self.quality = quality
        self._lock = threading.Lock()
        self._current_frame: Optional[bytes] = None
        self._session_id: Optional[str] = None
        self._is_active: bool = False
        self._idle_frame = self._create_idle_frame()

    def _create_idle_frame(self) -> bytes:
        """Generates a static dark placeholder frame."""
        canvas = np.zeros((480, 854, 3), dtype=np.uint8)
        # Background color #0F1B2D
        canvas[:] = (45, 27, 15)
        # Draw border #24384F
        cv2.rectangle(canvas, (20, 20), (834, 460), (79, 56, 36), 1)

        text = "SANKET INVIGILATION ASSISTANT"
        subtext = "No active session streaming. Select a recording to begin."
        cv2.putText(canvas, text, (230, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (243, 237, 232), 2, cv2.LINE_AA)
        cv2.putText(canvas, subtext, (200, 270), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (166, 143, 124), 1, cv2.LINE_AA)

        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), self.quality]
        _, jpeg = cv2.imencode(".jpg", canvas, encode_param)
        return jpeg.tobytes()

    def update_frame(self, session_id: str, image: np.ndarray) -> None:
        """Encodes and stores the latest annotated frame in the slot."""
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), self.quality]
        _, jpeg = cv2.imencode(".jpg", image, encode_param)
        frame_bytes = jpeg.tobytes()

        with self._lock:
            self._current_frame = frame_bytes
            self._session_id = session_id
            self._is_active = True

    def set_idle(self) -> None:
        with self._lock:
            self._is_active = False
            self._current_frame = None
            self._session_id = None

    def generate_mjpeg(self, session_id: Optional[str] = None) -> Iterator[bytes]:
        """Yields multipart MJPEG chunks at self.fps rate."""
        delay = 1.0 / float(self.fps)
        while True:
            with self._lock:
                if self._is_active and self._current_frame is not None:
                    if session_id is None or self._session_id == session_id:
                        data = self._current_frame
                    else:
                        data = self._idle_frame
                else:
                    data = self._idle_frame

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + data + b"\r\n"
            )
            time.sleep(delay)


streamer = FrameStreamer()
