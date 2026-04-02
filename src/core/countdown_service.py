from __future__ import annotations

from datetime import datetime


class CountdownService:
    def __init__(self, delivery_date: str) -> None:
        self.delivery_date = datetime.strptime(delivery_date, "%Y-%m-%d")

    def get_remaining(self, now: datetime | None = None) -> dict:
        now = now or datetime.now()
        delta = self.delivery_date - now
        remaining_sec = int(delta.total_seconds())
        if remaining_sec <= 0:
            return {"expired": True, "days": 0, "hours": 0, "minutes": 0, "seconds": 0}

        days = remaining_sec // 86400
        hours = (remaining_sec % 86400) // 3600
        minutes = (remaining_sec % 3600) // 60
        seconds = remaining_sec % 60
        return {
            "expired": False,
            "days": days,
            "hours": hours,
            "minutes": minutes,
            "seconds": seconds,
        }
