"""Daily log files with automatic gzip compression of previous days."""

from __future__ import annotations

import gzip
import logging
import threading
from datetime import date, datetime, timezone
from pathlib import Path


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def compress_log_file(path: Path) -> None:
    if not path.exists() or path.suffix != ".log":
        return
    gz_path = path.with_name(path.name + ".gz")
    if gz_path.exists():
        path.unlink(missing_ok=True)
        return
    with path.open("rb") as src, gzip.open(gz_path, "wb") as dst:
        dst.writelines(src)
    path.unlink()


def compress_old_logs(log_dir: Path, prefix: str, keep_today: bool = True) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    for path in sorted(log_dir.glob(f"{prefix}-*.log")):
        if keep_today and today in path.name:
            continue
        compress_log_file(path)


class DailyLogWriter:
    """Append-only writer that rolls over at UTC midnight and gzips old files."""

    def __init__(self, log_dir: str | Path, prefix: str) -> None:
        self._log_dir = Path(log_dir)
        self._prefix = prefix
        self._lock = threading.Lock()
        self._current_day: str | None = None
        self._handle = None
        self._log_dir.mkdir(parents=True, exist_ok=True)
        compress_old_logs(self._log_dir, self._prefix)

    def _path_for_day(self, day: str) -> Path:
        return self._log_dir / f"{self._prefix}-{day}.log"

    def _ensure_day(self, day: str) -> None:
        if self._current_day == day and self._handle is not None:
            return
        if self._handle is not None:
            self._handle.close()
            self._handle = None
        if self._current_day and self._current_day != day:
            compress_log_file(self._path_for_day(self._current_day))
        self._current_day = day
        self._handle = self._path_for_day(day).open("a", encoding="utf-8")

    def write_line(self, line: str) -> None:
        day = date.today().isoformat()
        with self._lock:
            self._ensure_day(day)
            assert self._handle is not None
            self._handle.write(line.rstrip() + "\n")
            self._handle.flush()

    def close(self) -> None:
        with self._lock:
            if self._handle is not None:
                self._handle.close()
                self._handle = None

    @property
    def log_dir(self) -> Path:
        return self._log_dir

    @property
    def prefix(self) -> str:
        return self._prefix

    def today_path(self) -> Path:
        return self._path_for_day(date.today().isoformat())


class DailyGzipLoggingHandler(logging.Handler):
    """Logging handler that writes to prefix-YYYY-MM-DD.log and gzips old days."""

    def __init__(self, log_dir: str | Path, prefix: str, level: int = logging.NOTSET) -> None:
        super().__init__(level)
        self._writer = DailyLogWriter(log_dir, prefix)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self._writer.write_line(msg)
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        self._writer.close()
        super().close()

    @property
    def writer(self) -> DailyLogWriter:
        return self._writer
