from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time

from src.models.task import Task


class ProgressService:
    @staticmethod
    def compute_by_category(tasks: list[Task]) -> dict:
        by_category: dict[str, dict] = defaultdict(
            lambda: {
                "total": 0,
                "completed": 0,
                "focus_time_spent": 0,
                "completion_rate": 0.0,
            }
        )

        for task in tasks:
            slot = by_category[task.category]
            slot["total"] += 1
            slot["focus_time_spent"] += int(task.focus_time_spent)
            if task.status == "completed":
                slot["completed"] += 1

        for slot in by_category.values():
            total = slot["total"]
            slot["completion_rate"] = round((slot["completed"] / total * 100) if total else 0.0, 2)

        return dict(by_category)

    @staticmethod
    def sort_tasks(tasks: list[Task]) -> list[Task]:
        weight_rank = {"urgent": 0, "important": 1, "normal": 2}

        def task_key(task: Task) -> tuple:
            deadline_dt = datetime.strptime(task.deadline, "%Y-%m-%d")
            return (
                weight_rank.get(task.weight, 9),
                deadline_dt,
                task.task_name.lower(),
            )

        return sorted(tasks, key=task_key)

    @staticmethod
    def is_deadline_within_24h(task: Task, now: datetime | None = None) -> bool:
        now = now or datetime.now()
        deadline_date = datetime.strptime(task.deadline, "%Y-%m-%d").date()
        deadline_dt = datetime.combine(deadline_date, time.max)
        delta = deadline_dt - now
        return 0 <= delta.total_seconds() <= 24 * 3600
