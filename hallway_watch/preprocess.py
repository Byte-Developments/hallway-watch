"""Frame preprocessing for low-light hallway monitoring."""

from __future__ import annotations

import cv2
import numpy as np


def to_grayscale(frame: np.ndarray) -> np.ndarray:
    if len(frame.shape) == 2:
        return frame
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


def enhance_low_light(
    frame: np.ndarray,
    clip_limit: float = 2.0,
    tile_size: int = 8,
) -> np.ndarray:
    """Convert to grayscale, boost contrast with CLAHE, return 3-channel BGR."""
    gray = to_grayscale(frame)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tile_size, tile_size))
    enhanced = clahe.apply(gray)
    return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)


def prepare_frame(frame: np.ndarray, low_light_enhance: bool = True) -> np.ndarray:
    """Return a black-and-white enhanced frame for motion and detection."""
    if low_light_enhance:
        return enhance_low_light(frame)
    gray = to_grayscale(frame)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
