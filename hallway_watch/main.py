"""Hallway watch — detect heads, play sound, send push notification."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import cv2

from hallway_watch.audio import play_sound
from hallway_watch.config import AppConfig, load_config
from hallway_watch.detector import HeadDetector, load_roi_mask
from hallway_watch.motion import MotionGate
from hallway_watch.preprocess import prepare_frame
from hallway_watch.web import NotificationServer


def setup_logging(config: AppConfig) -> None:
    level = getattr(logging, config.logging.level.upper(), logging.INFO)
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if config.logging.file:
        handlers.append(logging.FileHandler(config.logging.file))
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )


def open_camera(config: AppConfig) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(config.camera.device)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.camera.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.camera.height)
    cap.set(cv2.CAP_PROP_FPS, config.camera.fps)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera device {config.camera.device}")
    return cap


def trigger_alert(
    config: AppConfig,
    logger: logging.Logger,
    notification_server: NotificationServer | None,
) -> None:
    logger.info("Head detected — triggering alert")
    if config.audio.enabled:
        play_sound(config.audio.sound_file, config.audio.device)
    if config.notifications.enabled and notification_server is not None:
        notification_server.notify()


def run(config: AppConfig, preview: bool = False) -> None:
    logger = logging.getLogger("hallway_watch")
    cap = open_camera(config)

    ret, frame = cap.read()
    if not ret:
        cap.release()
        raise RuntimeError("Could not read initial frame from camera")

    roi_mask = load_roi_mask(config.detection.roi_mask, frame.shape)
    motion = MotionGate(threshold=config.detection.motion_threshold)
    motion.set_roi_mask(roi_mask)

    detector = HeadDetector(
        config.detection.model,
        config.detection.confidence,
        config.detection.head_height_fraction,
    )
    detector.set_roi_mask(roi_mask)

    last_alert = 0.0
    cooldown = config.detection.alert_cooldown_seconds
    frame_interval = 1.0 / max(config.camera.fps, 1)

    notification_server: NotificationServer | None = None
    if config.notifications.enabled:
        notification_server = NotificationServer(config.notifications)
        notification_server.start()

    logger.info("Hallway watch started (preview=%s)", preview)

    try:
        while True:
            loop_start = time.monotonic()
            ret, frame = cap.read()
            if not ret:
                logger.warning("Frame read failed — retrying")
                time.sleep(0.5)
                continue

            processed = prepare_frame(frame, config.detection.low_light_enhance)
            display = processed if config.detection.low_light_enhance else frame

            head_detected = False
            detections: list[tuple[int, int, int, int, float]] = []
            if motion.has_motion(processed):
                detections = detector.detect(processed)
                head_detected = len(detections) > 0

            now = time.monotonic()
            if head_detected and (now - last_alert) >= cooldown:
                trigger_alert(config, logger, notification_server)
                last_alert = now

            if preview:
                for x1, y1, x2, y2, conf in detections:
                    cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(
                        display,
                        f"head {conf:.0%}",
                        (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 255, 0),
                        1,
                    )
                if roi_mask is not None:
                    overlay = display.copy()
                    overlay[roi_mask == 0] = (overlay[roi_mask == 0] * 0.4).astype(overlay.dtype)
                    display = overlay
                cv2.imshow("hallway-watch", display)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            elapsed = time.monotonic() - loop_start
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        logger.info("Shutting down")
    finally:
        if notification_server is not None:
            notification_server.stop()
        cap.release()
        if preview:
            cv2.destroyAllWindows()


def main() -> None:
    parser = argparse.ArgumentParser(description="Hallway head detection")
    parser.add_argument(
        "-c", "--config", default="config.yaml", help="Path to config file"
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Show camera preview with detection boxes (requires display)",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    setup_logging(config)
    run(config, preview=args.preview)


if __name__ == "__main__":
    main()
