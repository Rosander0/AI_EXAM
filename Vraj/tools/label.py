"""Ground-Truth Video Annotation Tool for SANKET.

Usage:
  python tools/label.py --video <path_to_video> [--output <json_path>]
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, List
import cv2


def main() -> int:
    parser = argparse.ArgumentParser(description="SANKET Ground-Truth Annotation Tool")
    parser.add_argument("--video", type=str, required=True, help="Path to video file to annotate")
    parser.add_argument("--output", type=str, default=None, help="Output JSON path (default: datasets/labels/<name>.json)")
    args = parser.parse_args()

    vpath = Path(args.video)
    if not vpath.is_file():
        print(f"Error: Video file not found at '{vpath}'", file=sys.stderr)
        return 1

    out_path = Path(args.output) if args.output else Path("datasets/labels") / f"{vpath.stem}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    labels: List[Dict[str, Any]] = []
    if out_path.is_file():
        try:
            labels = json.loads(out_path.read_text(encoding="utf-8"))
            print(f"[INFO] Loaded {len(labels)} existing labels from {out_path}")
        except Exception:
            labels = []

    cap = cv2.VideoCapture(str(vpath))
    if not cap.isOpened():
        print(f"Error: OpenCV could not open video '{vpath}'", file=sys.stderr)
        return 1

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    print("\n" + "=" * 70)
    print("SANKET Ground-Truth Video Annotation Tool")
    print("Controls:")
    print("  [SPACE]     : Pause / Play")
    print("  [D] / [A]   : Step Forward / Backward 1 frame")
    print("  [L]         : Mark Event Interval at current position")
    print("  [S]         : Save labels to disk")
    print("  [Q]         : Quit")
    print("=" * 70 + "\n")

    paused = True
    current_frame = 0

    while True:
        cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
        ret, frame = cap.read()
        if not ret:
            break

        t = current_frame / fps
        mins = int(t // 60)
        secs = int(t % 60)
        millis = int((t - int(t)) * 1000)

        display = frame.copy()
        cv2.putText(
            display,
            f"F: {current_frame:05d}/{total_frames} | T: {mins:02d}:{secs:02d}.{millis:03d} | Labels: {len(labels)}",
            (15, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )

        cv2.imshow("SANKET Ground-Truth Labeling Tool", display)
        delay = 0 if paused else int(1000 / fps)
        key = cv2.waitKey(delay) & 0xFF

        if key == ord("q"):
            break
        elif key == ord(" "):
            paused = not paused
        elif key == ord("d"):
            current_frame = min(total_frames - 1, current_frame + 1)
        elif key == ord("a"):
            current_frame = max(0, current_frame - 1)
        elif key == ord("l"):
            # Interactive prompt in console
            print(f"\n--- Adding label at frame {current_frame} (T = {t:.2f}s) ---")
            try:
                t_end_in = input(f"Enter end time in seconds (default {t + 2.0:.2f}s): ").strip()
                t_end = float(t_end_in) if t_end_in else t + 2.0
                seat_id = input("Enter seat ID (e.g. S01, S02): ").strip().upper() or "S01"
                rule = input("Enter rule (head_turn / object_phone / object_chit / neighbour_reach / turning_back): ").strip() or "head_turn"
                desc = input("Enter brief description: ").strip() or "Observed behavioral event"

                labels.append({
                    "t_start": round(t, 2),
                    "t_end": round(t_end, 2),
                    "seat_id": seat_id,
                    "rule": rule,
                    "description": desc,
                })
                print(f"[SAVED EVENT] [{t:.2f}s - {t_end:.2f}s] {seat_id} ({rule}): {desc}")
            except Exception as e:
                print(f"[ERROR] Invalid input: {e}")
        elif key == ord("s"):
            out_path.write_text(json.dumps(labels, indent=2), encoding="utf-8")
            print(f"[INFO] Saved {len(labels)} labels to {out_path}")

        if not paused:
            current_frame += 1
            if current_frame >= total_frames:
                paused = True
                current_frame = total_frames - 1

    cap.release()
    cv2.destroyAllWindows()

    out_path.write_text(json.dumps(labels, indent=2), encoding="utf-8")
    print(f"\n[DONE] Saved {len(labels)} labels to {out_path}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
