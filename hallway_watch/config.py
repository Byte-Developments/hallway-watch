from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class CameraConfig:
    device: int | str = 0
    width: int = 800
    height: int = 600
    fps: int = 8
    recovery_enabled: bool = True
    recovery_max_failures: int = 15


@dataclass
class DetectionConfig:
    model: str = "models/yolov8n.pt"
    # Lower confidence catches distant / dim heads; confirm_frames reduces false alerts
    confidence: float = 0.42
    motion_threshold: int = 18
    motion_min_area: int = 600
    # Min seconds between alerts for separate visits (backup guard)
    alert_cooldown_seconds: int = 15
    # Frames without a head before the hallway counts as empty again (~1.5s @ 8fps)
    visit_clear_frames: int = 12
    roi_mask: str | None = None
    low_light_enhance: bool = True
    clahe_clip_limit: float = 4.0
    clahe_tile_size: int = 8
    gamma: float = 1.35
    denoise: bool = True
    head_height_fraction: float = 0.45
    # Boxes smaller than this (px) are treated as distant head-only detections
    small_box_height: int = 100
    imgsz: int = 736
    confirm_frames: int = 2


@dataclass
class AudioConfig:
    enabled: bool = True
    sound_file: str = "assets/sounds/alert.wav"
    device: str = "default"


@dataclass
class NotificationConfig:
    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 8765
    title: str = "Hallway Alert"
    message: str = "Someone is in the hallway"
    # HTTPS is required for service workers / push off localhost
    tls_enabled: bool = True
    tls_cert: str = "certs/cert.pem"
    tls_key: str = "certs/key.pem"
    vapid_contact: str = "mailto:hallway-watch@localhost"


@dataclass
class SnapshotsConfig:
    enabled: bool = True
    dir: str = "snapshots"
    retention_days: int = 7


@dataclass
class LoggingConfig:
    level: str = "INFO"
    debug_level: str = "DEBUG"
    detection_log_dir: str = "logs/detections"
    debug_log_dir: str = "logs/debug"


@dataclass
class AppConfig:
    camera: CameraConfig
    detection: DetectionConfig
    audio: AudioConfig
    notifications: NotificationConfig
    snapshots: SnapshotsConfig
    logging: LoggingConfig


def load_config(path: str | Path = "config.yaml") -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config not found: {config_path}. Copy config.yaml.example to config.yaml."
        )

    with config_path.open() as f:
        raw = yaml.safe_load(f) or {}

    return AppConfig(
        camera=CameraConfig(**raw.get("camera", {})),
        detection=DetectionConfig(**raw.get("detection", {})),
        audio=AudioConfig(**raw.get("audio", {})),
        notifications=NotificationConfig(**raw.get("notifications", {})),
        snapshots=SnapshotsConfig(**raw.get("snapshots", {})),
        logging=LoggingConfig(**raw.get("logging", {})),
    )
