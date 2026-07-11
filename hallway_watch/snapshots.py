"""Save annotated camera frames when an alert fires."""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np

from hallway_watch.timezone_util import eastern_now

logger = logging.getLogger(__name__)


def _snapshot_filename() -> str:
    return eastern_now().strftime("alert-%Y-%m-%d_%H-%M-%S.jpg")


def save_alert_snapshot(
    frame: np.ndarray,
    detections: list[tuple[int, int, int, int, float]],
    snapshot_dir: str | Path,
) -> Path | None:
    """Draw head boxes on the frame and save a JPEG. Returns path or None on failure."""
    directory = Path(snapshot_dir)
    directory.mkdir(parents=True, exist_ok=True)

    annotated = frame.copy()
    for x1, y1, x2, y2, conf in detections:
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(
            annotated,
            f"head {conf:.0%}",
            (x1, max(y1 - 8, 0)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            1,
        )

    path = directory / _snapshot_filename()
    if not cv2.imwrite(str(path), annotated, [cv2.IMWRITE_JPEG_QUALITY, 85]):
        logger.error("Failed to write snapshot: %s", path)
        return None

    logger.info("Saved alert snapshot: %s", path)
    return path
