"""Application logging — stdout + daily debug log files."""

from __future__ import annotations

import logging
import sys

from hallway_watch.config import AppConfig
from hallway_watch.daily_log import DailyGzipLoggingHandler
from hallway_watch.detection_log import DetectionLogger
from hallway_watch.timezone_util import EasternFormatter

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def setup_logging(config: AppConfig) -> DetectionLogger:
    level = getattr(logging, config.logging.level.upper(), logging.INFO)
    debug_level = getattr(
        logging, config.logging.debug_level.upper(), logging.DEBUG
    )

    detection_logger = DetectionLogger(config.logging.detection_log_dir)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(debug_level)

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(EasternFormatter(_LOG_FORMAT))
    root.addHandler(console)

    debug_handler = DailyGzipLoggingHandler(
        config.logging.debug_log_dir,
        "debug",
        level=debug_level,
    )
    debug_handler.setFormatter(EasternFormatter(_LOG_FORMAT))
    root.addHandler(debug_handler)

    # Quiet noisy third-party loggers unless debugging hard
    if level > logging.DEBUG:
        logging.getLogger("ultralytics").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)

    return detection_logger
