"""Hallway watch — detect heads, play sound, send push notification."""

from __future__ import annotations

import argparse
import logging
import sys
import time

import cv2

from hallway_watch.audio import play_sound
from hallway_watch.config import AppConfig, load_config
from hallway_watch.detection_log import DetectionLogger
from hallway_watch.detector import HeadDetector, load_roi_mask
from hallway_watch.logging_setup import setup_logging
from hallway_watch.motion import MotionGate
from hallway_watch.preprocess import prepare_frame
from hallway_watch.snapshots import save_alert_snapshot
from hallway_watch.visit import VisitTracker
from hallway_watch.web import NotificationServer


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
    detection_logger: DetectionLogger,
    notification_server: NotificationServer | None,
    detections: list[tuple[int, int, int, int, float]],
    frame: np.ndarray,
) -> None:
    max_conf = max(conf for _, _, _, _, conf in detections)

    snapshot_path: str | None = None
    if config.snapshots.enabled:
        saved = save_alert_snapshot(frame, detections, config.snapshots.dir)
        if saved is not None:
            snapshot_path = str(saved)

    detection_logger.log_alert(len(detections), max_conf, snapshot_path)
    logger.info(
        "Head detected — triggering alert (count=%d max_conf=%.0f%%)",
        len(detections),
        max_conf * 100,
    )
    if snapshot_path:
        logger.info("Alert snapshot: %s", snapshot_path)
    if config.audio.enabled:
        play_sound(config.audio.sound_file, config.audio.device)
    if config.notifications.enabled and notification_server is not None:
        notification_server.notify()


def run(
    config: AppConfig,
    detection_logger: DetectionLogger,
    preview: bool = False,
) -> None:
    logger = logging.getLogger("hallway_watch")
    cap = open_camera(config)

    ret, frame = cap.read()
    if not ret:
        cap.release()
        raise RuntimeError("Could not read initial frame from camera")

    roi_mask = load_roi_mask(config.detection.roi_mask, frame.shape)
    motion = MotionGate(
        threshold=config.detection.motion_threshold,
        min_area=config.detection.motion_min_area,
    )
    motion.set_roi_mask(roi_mask)

    det = config.detection
    detector = HeadDetector(
        det.model,
        det.confidence,
        det.head_height_fraction,
        det.small_box_height,
        det.imgsz,
    )
    detector.set_roi_mask(roi_mask)

    visit_tracker = VisitTracker(
        confirm_frames=det.confirm_frames,
        clear_frames=det.visit_clear_frames,
        min_seconds_between_visits=det.alert_cooldown_seconds,
    )
    frame_interval = 1.0 / max(config.camera.fps, 1)

    notification_server: NotificationServer | None = None
    if config.notifications.enabled:
        notification_server = NotificationServer(config.notifications)
        notification_server.start()

    logger.info("Hallway watch started (preview=%s)", preview)
    logger.debug(
        "Logging detections to %s, debug to %s",
        config.logging.detection_log_dir,
        config.logging.debug_log_dir,
    )

    try:
        while True:
            loop_start = time.monotonic()
            ret, frame = cap.read()
            if not ret:
                logger.warning("Frame read failed — retrying")
                time.sleep(0.5)
                continue

            processed = prepare_frame(
                frame,
                det.low_light_enhance,
                clahe_clip_limit=det.clahe_clip_limit,
                clahe_tile_size=det.clahe_tile_size,
                gamma=det.gamma,
                denoise=det.denoise,
            )
            display = processed if det.low_light_enhance else frame

            head_seen = False
            detections: list[tuple[int, int, int, int, float]] = []
            if motion.has_motion(processed):
                logger.debug("Motion detected — running inference")
                detections = detector.detect(processed)
                if detections:
                    detection_logger.log_heads(detections)
                    logger.debug(
                        "Heads detected: %d (max conf %.0f%%)",
                        len(detections),
                        max(c for *_, c in detections) * 100,
                    )
                head_seen = len(detections) > 0

            now = time.monotonic()
            should_alert, visit_cleared = visit_tracker.update(head_seen, now)
            if visit_cleared:
                detection_logger.log_visit_clear()
                logger.debug("Visit cleared — hallway empty")

            if should_alert and detections:
                trigger_alert(
                    config,
                    logger,
                    detection_logger,
                    notification_server,
                    detections,
                    frame,
                )

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
        detection_logger.close()
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
    detection_logger = setup_logging(config)
    run(config, detection_logger, preview=args.preview)


if __name__ == "__main__":
    main()
