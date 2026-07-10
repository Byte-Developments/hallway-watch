from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class CameraConfig:
    device: int = 0
    width: int = 640
    height: int = 480
    fps: int = 10


@dataclass
class DetectionConfig:
    model: str = "models/yolov8n.pt"
    confidence: float = 0.55
    motion_threshold: int = 25
    alert_cooldown_seconds: int = 30
    roi_mask: str | None = None
    # Grayscale + CLAHE before motion/AI — helps in dark hallways
    low_light_enhance: bool = True
    # Top fraction of a person box treated as the head (0.25–0.45 typical)
    head_height_fraction: float = 0.35


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
    vapid_contact: str = "mailto:hallway-watch@local"


@dataclass
class LoggingConfig:
    level: str = "INFO"
    file: str = "hallway-watch.log"


@dataclass
class AppConfig:
    camera: CameraConfig
    detection: DetectionConfig
    audio: AudioConfig
    notifications: NotificationConfig
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
        logging=LoggingConfig(**raw.get("logging", {})),
    )
