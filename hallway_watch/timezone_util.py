"""Eastern Time (America/New_York) helpers for logs and filenames."""

from __future__ import annotations

from datetime import datetime
from logging import Formatter
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")


def eastern_now() -> datetime:
    return datetime.now(EASTERN)


def eastern_now_iso() -> str:
    """ISO-8601 timestamp with offset, e.g. 2026-07-10T20:25:00.123-04:00."""
    return eastern_now().isoformat(timespec="milliseconds")


def eastern_today() -> str:
    """Today's date in Eastern Time (YYYY-MM-DD)."""
    return eastern_now().date().isoformat()


class EasternFormatter(Formatter):
    """Log formatter that prints timestamps in Eastern Time."""

    def formatTime(self, record, datefmt: str | None = None) -> str:
        dt = datetime.fromtimestamp(record.created, tz=EASTERN)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%d %H:%M:%S %Z")
