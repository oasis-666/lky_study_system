from __future__ import annotations

from datetime import date, datetime


class FocusTimerService:
    def __init__(self) -> None:
        self._running = False
        self._active_task_id: str | None = None
        self._started_at: datetime | None = None
        self._today_seconds = 0
        self._current_day = date.today()

    def start(self, task_id: str) -> None:
        self._roll_if_day_changed()
        if self._running:
            return
        self._running = True
        self._active_task_id = task_id
        self._started_at = datetime.now()

    def pause(self) -> int:
        self._roll_if_day_changed()
        if not self._running or self._started_at is None:
            return 0

        elapsed = int((datetime.now() - self._started_at).total_seconds())
        self._today_seconds += max(0, elapsed)
        self._running = False
        self._started_at = None
        return max(0, elapsed)

    def resume(self) -> None:
        self._roll_if_day_changed()
        if self._running or self._active_task_id is None:
            return
        self._running = True
        self._started_at = datetime.now()

    def stop(self) -> tuple[str | None, int]:
        elapsed = self.pause()
        task_id = self._active_task_id
        self._active_task_id = None
        return task_id, elapsed

    def today_seconds(self) -> int:
        self._roll_if_day_changed()
        if self._running and self._started_at is not None:
            dynamic = int((datetime.now() - self._started_at).total_seconds())
            return self._today_seconds + max(0, dynamic)
        return self._today_seconds

    def active_task_id(self) -> str | None:
        return self._active_task_id

    def is_running(self) -> bool:
        return self._running

    def _roll_if_day_changed(self) -> None:
        now_day = date.today()
        if now_day != self._current_day:
            self._today_seconds = 0
            self._current_day = now_day
            self._running = False
            self._active_task_id = None
            self._started_at = None
