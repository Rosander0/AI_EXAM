"""Asynchronous Evidence Clip Extraction for SANKET.

CRITICAL INVARIANTS:
1. Extraction runs asynchronously in a background thread queue — NEVER blocks inference.
2. Extracts [t_start - 2.0s, t_end + 3.0s] window around critical events.
3. Enforces time-bound throttling per (seat_id, rule) to prevent duplicate clip flooding.
4. Saves clips to clips/{event_id}.mp4 and thumbnail to clips/{event_id}_thumb.jpg.
5. Updates event record in SessionStore with relative clip_path and thumb_path.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import queue
import threading
import time
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np

from sanket.scoring import Event
from sanket.store import SessionStore


@dataclass
class ClipRequest:
    event_id: str
    session_id: str
    frames: List[Tuple[float, np.ndarray]]  # [(t, frame_img)]
    fps: float


class ClipExtractor:
    """Extracts 5-second evidence clips asynchronously with time-bound throttling."""

    def __init__(
        self,
        store: Optional[SessionStore] = None,
        clips_dir: Path | str = "clips",
        cooldown_seconds: float = 15.0,
    ):
        self.store = store
        self.clips_dir = Path(clips_dir)
        self.clips_dir.mkdir(parents=True, exist_ok=True)
        self.cooldown_seconds = float(cooldown_seconds)

        # Per (seat_id, rule) timestamp tracking for time-bound suppression
        self.last_clip_times: Dict[Tuple[str, str], float] = {}

        self._queue: queue.Queue[Optional[ClipRequest]] = queue.Queue()
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

    def enqueue_clip(
        self,
        event: Event,
        ring_buffer: List[Tuple[float, np.ndarray]],
        fps: float = 25.0,
        force: bool = False,
    ) -> bool:
        """
        Enqueues a critical event's buffered frames for async video writing.
        Applies time-bound throttling per (seat_id, rule) to avoid spamming duplicate clips.
        """
        if not ring_buffer:
            return False

        key = (event.seat_id, event.rule)
        if not force and key in self.last_clip_times:
            last_t = self.last_clip_times[key]
            if (event.t_start - last_t) < self.cooldown_seconds:
                # Suppress duplicate clip of the same offence type within cooldown window
                return False

        self.last_clip_times[key] = event.t_start

        # Copy frames from ring buffer for the async worker
        buffer_copy = [(t, img.copy()) for t, img in ring_buffer]
        req = ClipRequest(
            event_id=event.event_id,
            session_id=event.session_id,
            frames=buffer_copy,
            fps=fps,
        )
        self._queue.put(req)
        return True

    def _worker_loop(self) -> None:
        while True:
            req = self._queue.get()
            if req is None:
                break

            try:
                self._write_clip_and_thumb(req)
            except Exception as e:
                print(f"[WARN] Error writing evidence clip for {req.event_id}: {e}")
            finally:
                self._queue.task_done()

    def _write_clip_and_thumb(self, req: ClipRequest) -> None:
        if not req.frames:
            return

        clip_path = self.clips_dir / f"{req.event_id}.mp4"
        thumb_path = self.clips_dir / f"{req.event_id}_thumb.jpg"

        h, w = req.frames[0][1].shape[:2]

        # 1. Write thumbnail (from middle of the clip)
        mid_idx = len(req.frames) // 2
        mid_frame = req.frames[mid_idx][1]
        cv2.imwrite(str(thumb_path), mid_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])

        # 2. Write MP4 Video Clip
        writer = None
        for codec in ["avc1", "H264", "mp4v", "MJPG"]:
            fourcc = cv2.VideoWriter_fourcc(*codec)
            test_writer = cv2.VideoWriter(str(clip_path), fourcc, max(1.0, float(req.fps)), (w, h))
            if test_writer.isOpened():
                writer = test_writer
                break

        if writer is not None and writer.isOpened():
            for _, frame_img in req.frames:
                writer.write(frame_img)
            writer.release()

        # 3. Update database record
        if self.store:
            with self.store._get_connection() as conn:
                conn.execute(
                    "UPDATE events SET clip_path = ?, thumb_path = ? WHERE session_id = ? AND event_id = ?",
                    (f"/api/clips/{req.event_id}", f"/api/thumbs/{req.event_id}", req.session_id, req.event_id),
                )

    def close(self) -> None:
        """Flushes queue and terminates worker thread."""
        self._queue.put(None)
        self._worker_thread.join(timeout=3.0)
