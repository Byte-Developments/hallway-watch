"""One alert per hallway visit — no spam while someone is present."""

from __future__ import annotations


class VisitTracker:
    """Alert once when someone enters; stay silent until they leave."""

    def __init__(
        self,
        confirm_frames: int = 2,
        clear_frames: int = 12,
        min_seconds_between_visits: float = 15.0,
    ) -> None:
        self.confirm_frames = max(confirm_frames, 1)
        self.clear_frames = max(clear_frames, 1)
        self.min_seconds_between_visits = min_seconds_between_visits

        self._present_streak = 0
        self._absent_streak = 0
        self._visit_active = False
        self._last_alert_time = 0.0

    @property
    def visit_active(self) -> bool:
        return self._visit_active

    def update(self, head_seen: bool, now: float) -> tuple[bool, bool]:
        """Process one frame. Returns (should_alert, visit_just_cleared)."""
        visit_cleared = False

        if head_seen:
            self._present_streak += 1
            self._absent_streak = 0
        else:
            self._absent_streak += 1
            self._present_streak = 0
            if self._absent_streak >= self.clear_frames and self._visit_active:
                visit_cleared = True
                self._visit_active = False

        confirmed = self._present_streak >= self.confirm_frames
        if not confirmed:
            return False, visit_cleared

        if self._visit_active:
            return False, visit_cleared

        if (now - self._last_alert_time) < self.min_seconds_between_visits:
            self._visit_active = True
            return False, visit_cleared

        self._visit_active = True
        self._last_alert_time = now
        return True, visit_cleared
