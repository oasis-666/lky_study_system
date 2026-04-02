from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

TaskStatus = Literal["todo", "in_progress", "completed"]
TaskWeight = Literal["urgent", "important", "normal"]


@dataclass
class Task:
    id: str
    task_name: str
    category: str
    status: TaskStatus
    weight: TaskWeight
    deadline: str
    focus_time_spent: int = 0
    notes_refs: list[str] = field(default_factory=list)
    completed_at: str = ""
    completion_summary: str = ""
    completion_meta: dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "task_name": self.task_name,
            "category": self.category,
            "status": self.status,
            "weight": self.weight,
            "deadline": self.deadline,
            "focus_time_spent": self.focus_time_spent,
            "notes_refs": self.notes_refs,
            "completed_at": self.completed_at,
            "completion_summary": self.completion_summary,
            "completion_meta": self.completion_meta,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class Note:
    id: str
    task_id: str
    content: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "content": self.content,
            "created_at": self.created_at,
        }
