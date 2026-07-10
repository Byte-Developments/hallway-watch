"""Frame preprocessing tuned for dark hallways and distant subjects."""

from __future__ import annotations

import cv2
import numpy as np


def to_grayscale(frame: np.ndarray) -> np.ndarray:
    if len(frame.shape) == 2:
        return frame
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


def apply_gamma(gray: np.ndarray, gamma: float) -> np.ndarray:
    if gamma <= 1.0:
        return gray
    inv_gamma = 1.0 / gamma
    table = np.array(
        [((i / 255.0) ** inv_gamma) * 255 for i in range(256)],
        dtype=np.uint8,
    )
    return cv2.LUT(gray, table)


def auto_gamma_for_brightness(gray: np.ndarray, base_gamma: float) -> float:
    """Boost gamma further when the scene is very dark."""
    mean = float(gray.mean())
    if mean < 45:
        return max(base_gamma, 1.75)
    if mean < 75:
        return max(base_gamma, 1.5)
    return base_gamma


def enhance_low_light(
    frame: np.ndarray,
    clip_limit: float = 4.0,
    tile_size: int = 8,
    gamma: float = 1.35,
    denoise: bool = True,
) -> np.ndarray:
    """Grayscale pipeline: denoise → gamma → CLAHE for night + distance."""
    gray = to_grayscale(frame)

    if denoise:
        gray = cv2.bilateralFilter(gray, d=5, sigmaColor=40, sigmaSpace=40)

    effective_gamma = auto_gamma_for_brightness(gray, gamma)
    gray = apply_gamma(gray, effective_gamma)

    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tile_size, tile_size))
    enhanced = clahe.apply(gray)
    return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)


def prepare_frame(
    frame: np.ndarray,
    low_light_enhance: bool = True,
    *,
    clahe_clip_limit: float = 4.0,
    clahe_tile_size: int = 8,
    gamma: float = 1.35,
    denoise: bool = True,
) -> np.ndarray:
    """Return a black-and-white enhanced frame for motion and detection."""
    if low_light_enhance:
        return enhance_low_light(
            frame,
            clip_limit=clahe_clip_limit,
            tile_size=clahe_tile_size,
            gamma=gamma,
            denoise=denoise,
        )
    gray = to_grayscale(frame)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
