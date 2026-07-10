"""Structured detection event log (one file per day)."""

from __future__ import annotations

from hallway_watch.daily_log import DailyLogWriter, _utc_now_iso


class DetectionLogger:
    def __init__(self, log_dir: str) -> None:
        self._writer = DailyLogWriter(log_dir, "detections")

    def log_head(
        self,
        confidence: float,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
    ) -> None:
        self._writer.write_line(
            f"{_utc_now_iso()}\tHEAD\t"
            f"conf={confidence:.3f}\tx1={x1}\ty1={y1}\tx2={x2}\ty2={y2}"
        )

    def log_heads(
        self,
        detections: list[tuple[int, int, int, int, float]],
    ) -> None:
        for x1, y1, x2, y2, conf in detections:
            self.log_head(conf, x1, y1, x2, y2)

    def log_alert(self, detection_count: int, max_conf: float) -> None:
        self._writer.write_line(
            f"{_utc_now_iso()}\tALERT\tcount={detection_count}\tmax_conf={max_conf:.3f}"
        )

    def log_visit_clear(self) -> None:
        self._writer.write_line(f"{_utc_now_iso()}\tVISIT_CLEAR")

    def log_motion(self) -> None:
        self._writer.write_line(f"{_utc_now_iso()}\tMOTION")

    def close(self) -> None:
        self._writer.close()

    @property
    def log_dir(self):
        return self._writer.log_dir
