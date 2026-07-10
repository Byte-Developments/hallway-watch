"""Lightweight motion gate — runs on grayscale-enhanced frames."""

from __future__ import annotations

import cv2
import numpy as np


class MotionGate:
    """Background-subtraction motion detector to reduce CPU usage."""

    def __init__(self, threshold: int = 25, min_area: int = 1500) -> None:
        self.threshold = threshold
        self.min_area = min_area
        self._bg: cv2.BackgroundSubtractor = cv2.createBackgroundSubtractorMOG2(
            history=120, varThreshold=16, detectShadows=False
        )
        self._roi_mask: np.ndarray | None = None

    def set_roi_mask(self, mask: np.ndarray | None) -> None:
        self._roi_mask = mask

    def has_motion(self, frame: np.ndarray) -> bool:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        fg_mask = self._bg.apply(gray)
        _, fg_mask = cv2.threshold(fg_mask, self.threshold, 255, cv2.THRESH_BINARY)

        if self._roi_mask is not None:
            fg_mask = cv2.bitwise_and(fg_mask, self._roi_mask)

        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            if cv2.contourArea(contour) >= self.min_area:
                return True
        return False
