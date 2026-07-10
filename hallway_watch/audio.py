"""Play alert sounds through the Pi's 3.5mm jack."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def play_sound(sound_file: str, device: str = "default") -> None:
    path = Path(sound_file)
    if not path.exists():
        logger.warning("Sound file not found: %s", path)
        return

    try:
        subprocess.Popen(
            ["aplay", "-q", "-D", device, str(path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        logger.error("aplay not found — install alsa-utils on the Pi")
