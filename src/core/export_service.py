from __future__ import annotations

from datetime import datetime
from pathlib import Path

from src.models.task import Note, Task


class ExportService:
    def __init__(self, logs_dir: Path) -> None:
        self.logs_dir = logs_dir

    def export_daily_markdown(self, date_str: str, tasks: list[Task], notes: list[Note]) -> Path:
        day = datetime.strptime(date_str, "%Y-%m-%d").date()
        completed_today = [
            task
            for task in tasks
            if task.status == "completed"
            and self._completion_date(task) == day
        ]

        task_ids = {task.id for task in completed_today}
        related_notes = [note for note in notes if note.task_id in task_ids]

        self.logs_dir.mkdir(parents=True, exist_ok=True)
        output = self.logs_dir / f"{date_str}.md"

        lines: list[str] = [f"# {date_str} 学习日报", "", "## 已完成任务"]
        if not completed_today:
            lines.append("- 今日无已完成任务")
        else:
            for task in completed_today:
                completed_at = task.completed_at or task.updated_at
                lines.append(f"- [{task.category}] {task.task_name} ({task.weight})")
                lines.append(f"  - 完成时间: {completed_at}")
                if task.completion_summary.strip():
                    lines.append(f"  - 完成总结: {task.completion_summary}")

        lines.extend(["", "## 关联笔记"])
        if not related_notes:
            lines.append("- 今日无关联笔记")
        else:
            for note in related_notes:
                lines.append(f"- Task {note.task_id}: {note.content}")

        output.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return output

    @staticmethod
    def _completion_date(task: Task):
        ts = task.completed_at or task.updated_at
        try:
            return datetime.fromisoformat(ts).date()
        except Exception:
            return None
