"""USB camera open + automatic recovery when reads fail."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import cv2

from hallway_watch.config import CameraConfig

logger = logging.getLogger(__name__)

DEFAULT_MAX_FAILURES = 15
DEFAULT_REOPEN_DELAY_S = 1.0
DEFAULT_RETRY_DELAY_S = 0.5


def _camera_source(device: int | str) -> int | str:
    """Prefer an explicit /dev/videoN path so OpenCV doesn't pick Pi codec nodes."""
    if isinstance(device, str):
        return device
    path = Path(f"/dev/video{device}")
    if path.exists():
        return str(path)
    return device


def open_camera(config: CameraConfig) -> cv2.VideoCapture:
    source = _camera_source(config.device)
    # CAP_V4L2 avoids GStreamer/obsensor probes that mis-handle Logitech UVC nodes
    cap = cv2.VideoCapture(source, cv2.CAP_V4L2)
    if not cap.isOpened() and source != config.device:
        logger.warning("V4L2 open failed for %s — retrying with configured device %s", source, config.device)
        cap = cv2.VideoCapture(config.device, cv2.CAP_V4L2)
    if not cap.isOpened():
        cap = cv2.VideoCapture(source)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.height)
    cap.set(cv2.CAP_PROP_FPS, config.fps)
    if not cap.isOpened():
        raise RuntimeError(
            f"Could not open camera device {config.device} (tried {source}). "
            "Check: v4l2-ctl --list-devices, that your user is in the 'video' group, "
            "and that hallway-watch.service is stopped while testing."
        )
    return cap


class CameraStream:
    """Wraps VideoCapture and reopens the device after sustained read failures."""

    def __init__(
        self,
        config: CameraConfig,
        *,
        recovery_enabled: bool = True,
        max_failures: int = DEFAULT_MAX_FAILURES,
        reopen_delay_s: float = DEFAULT_REOPEN_DELAY_S,
        retry_delay_s: float = DEFAULT_RETRY_DELAY_S,
    ) -> None:
        self._config = config
        self._recovery_enabled = recovery_enabled
        self._max_failures = max(1, max_failures)
        self._reopen_delay_s = reopen_delay_s
        self._retry_delay_s = retry_delay_s
        self._failures = 0
        self._cap = open_camera(config)

    @property
    def cap(self) -> cv2.VideoCapture:
        return self._cap

    def read(self):
        ret, frame = self._cap.read()
        if ret and frame is not None and frame.size > 0:
            self._failures = 0
            return True, frame

        self._failures += 1
        if self._recovery_enabled and self._failures >= self._max_failures:
            if self._recover():
                ret, frame = self._cap.read()
                if ret and frame is not None and frame.size > 0:
                    return True, frame
            self._failures = 0

        time.sleep(self._retry_delay_s)
        return False, None

    def _recover(self) -> bool:
        logger.warning(
            "Camera unresponsive after %d failed reads — reopening device %s",
            self._failures,
            self._config.device,
        )
        self._cap.release()
        time.sleep(self._reopen_delay_s)
        try:
            self._cap = open_camera(self._config)
        except RuntimeError as exc:
            logger.error("Camera reopen failed: %s", exc)
            return False

        ret, frame = self._cap.read()
        if ret and frame is not None and frame.size > 0:
            logger.info("Camera recovered")
            return True

        logger.error("Camera reopened but still not returning frames")
        return False

    def read_initial(self):
        """Read the first frame, recovering once if needed."""
        for attempt in range(2):
            ret, frame = self._cap.read()
            if ret and frame is not None and frame.size > 0:
                self._failures = 0
                return frame
            if attempt == 0 and self._recovery_enabled and self._recover():
                continue
        raise RuntimeError("Could not read initial frame from camera")

    def release(self) -> None:
        self._cap.release()
