"""Head detection using YOLOv8 nano (person class, head region extraction)."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO


PERSON_CLASS_ID = 0  # COCO "person"
ROI_WHITE_THRESHOLD = 127


class HeadDetector:
    def __init__(
        self,
        model_path: str,
        confidence: float = 0.55,
        head_height_fraction: float = 0.35,
    ) -> None:
        self.confidence = confidence
        self.head_height_fraction = head_height_fraction
        self._model = YOLO(model_path)
        self._roi_mask: np.ndarray | None = None

    def set_roi_mask(self, mask: np.ndarray | None) -> None:
        self._roi_mask = mask

    def _head_bbox(
        self, x1: int, y1: int, x2: int, y2: int
    ) -> tuple[int, int, int, int]:
        """Upper portion of a person box — where the head lives."""
        height = max(y2 - y1, 1)
        head_height = max(int(height * self.head_height_fraction), 12)
        return x1, y1, x2, min(y1 + head_height, y2)

    def _head_in_roi(self, x1: int, y1: int, x2: int, y2: int) -> bool:
        if self._roi_mask is None:
            return True

        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        h, w = self._roi_mask.shape[:2]
        if not (0 <= cx < w and 0 <= cy < h):
            return False
        return self._roi_mask[cy, cx] > 0

    def detect(self, frame: np.ndarray) -> list[tuple[int, int, int, int, float]]:
        """Return list of (x1, y1, x2, y2, confidence) for detected heads."""
        results = self._model.predict(
            frame,
            conf=self.confidence,
            classes=[PERSON_CLASS_ID],
            verbose=False,
            imgsz=640,
        )

        detections: list[tuple[int, int, int, int, float]] = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                px1, py1, px2, py2 = map(int, box.xyxy[0].tolist())
                conf = float(box.conf[0])
                x1, y1, x2, y2 = self._head_bbox(px1, py1, px2, py2)

                if not self._head_in_roi(x1, y1, x2, y2):
                    continue

                detections.append((x1, y1, x2, y2, conf))
        return detections


# Backwards-compatible alias
PersonDetector = HeadDetector


def load_roi_mask(path: str | None, frame_shape: tuple[int, ...]) -> np.ndarray | None:
    """Load a strict black-and-white ROI mask (white = watch, black = ignore)."""
    if not path:
        return None
    mask_path = Path(path)
    if not mask_path.exists():
        raise FileNotFoundError(f"ROI mask not found: {mask_path}")

    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        raise ValueError(f"Could not read ROI mask: {mask_path}")

    h, w = frame_shape[:2]
    if mask.shape[:2] != (h, w):
        mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)

    # Binarize so grey pixels don't create fuzzy edges in dark scenes
    _, mask = cv2.threshold(mask, ROI_WHITE_THRESHOLD, 255, cv2.THRESH_BINARY)
    return mask
