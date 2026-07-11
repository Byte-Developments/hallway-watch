"""Save annotated camera frames when an alert fires."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import cv2
import numpy as np

from hallway_watch.timezone_util import EASTERN, eastern_now

logger = logging.getLogger(__name__)

SNAPSHOT_NAME_RE = re.compile(r"^alert-(\d{4}-\d{2}-\d{2})_")


def _snapshot_filename() -> str:
    return eastern_now().strftime("alert-%Y-%m-%d_%H-%M-%S.jpg")


def _snapshot_date(path: Path) -> date:
    match = SNAPSHOT_NAME_RE.match(path.name)
    if match:
        return date.fromisoformat(match.group(1))
    return datetime.fromtimestamp(path.stat().st_mtime, tz=EASTERN).date()


def cleanup_old_snapshots(snapshot_dir: str | Path, retention_days: int = 7) -> int:
    """Delete alert JPEGs older than retention_days (Eastern dates). Returns count removed."""
    if retention_days <= 0:
        return 0

    directory = Path(snapshot_dir)
    if not directory.is_dir():
        return 0

    cutoff = eastern_now().date() - timedelta(days=retention_days)
    removed = 0
    for path in directory.glob("alert-*.jpg"):
        try:
            if _snapshot_date(path) < cutoff:
                path.unlink()
                removed += 1
        except OSError as exc:
            logger.warning("Could not remove old snapshot %s: %s", path, exc)

    if removed:
        logger.info(
            "Removed %d snapshot(s) older than %d days from %s",
            removed,
            retention_days,
            directory,
        )
    return removed


def save_alert_snapshot(
    frame: np.ndarray,
    detections: list[tuple[int, int, int, int, float]],
    snapshot_dir: str | Path,
    *,
    retention_days: int = 7,
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
    cleanup_old_snapshots(directory, retention_days)
    return path
