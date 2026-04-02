from __future__ import annotations

import json
import shutil
import uuid
from datetime import date, datetime
from pathlib import Path

from src.models.task import Note, Task

REQUIRED_TASK_KEYS = {
    "task_name",
    "category",
    "status",
    "weight",
    "deadline",
    "focus_time_spent",
}

DEFAULT_TASK_FIELDS = {
    "focus_time_spent": 0,
    "notes_refs": [],
    "completed_at": "",
    "completion_summary": "",
    "completion_meta": {},
}


class DataValidationError(ValueError):
    pass


class DataManager:
    def __init__(self, tasks_file: Path) -> None:
        self.tasks_file = tasks_file
        self.backup_file = self.tasks_file.with_suffix(self.tasks_file.suffix + ".bak")

    def ensure_storage(self) -> None:
        self.tasks_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.tasks_file.exists():
            self._write_payload({"schema_version": 1, "tasks": [], "notes": []})
        elif not self.backup_file.exists():
            shutil.copy2(self.tasks_file, self.backup_file)

    def load_payload(self) -> dict:
        self.ensure_storage()
        try:
            with self.tasks_file.open("r", encoding="utf-8") as f:
                payload = json.load(f)
        except json.JSONDecodeError as exc:
            restored = self._restore_from_backup()
            if not restored:
                raise DataValidationError(f"tasks.json parse failed: {exc}") from exc
            try:
                with self.tasks_file.open("r", encoding="utf-8") as f:
                    payload = json.load(f)
            except json.JSONDecodeError as second_exc:
                raise DataValidationError(
                    f"tasks.json parse failed after backup restore: {second_exc}"
                ) from second_exc

        payload, changed = self._normalize_payload(payload)

        for task in payload["tasks"]:
            missing = REQUIRED_TASK_KEYS - set(task.keys())
            if missing:
                raise DataValidationError(f"task missing fields: {sorted(missing)}")

        if changed:
            self._write_payload(payload)

        return payload

    def list_tasks(self) -> list[Task]:
        payload = self.load_payload()
        return [Task(**task) for task in payload["tasks"]]

    def list_notes(self) -> list[Note]:
        payload = self.load_payload()
        return [Note(**note) for note in payload["notes"]]

    def upsert_task(self, task_data: dict) -> Task:
        payload = self.load_payload()
        now = datetime.now().isoformat(timespec="seconds")

        if "id" not in task_data or not task_data["id"]:
            task_data["id"] = str(uuid.uuid4())
            task_data["created_at"] = now
        task_data["updated_at"] = now

        existing_idx = next(
            (i for i, item in enumerate(payload["tasks"]) if item.get("id") == task_data["id"]),
            None,
        )

        if existing_idx is None:
            payload["tasks"].append(task_data)
        else:
            created_at = payload["tasks"][existing_idx].get("created_at", now)
            task_data["created_at"] = created_at
            payload["tasks"][existing_idx] = task_data

        self._write_payload(payload)
        return Task(**task_data)

    def delete_task(self, task_id: str) -> bool:
        payload = self.load_payload()
        original_len = len(payload["tasks"])
        payload["tasks"] = [task for task in payload["tasks"] if task.get("id") != task_id]
        changed = len(payload["tasks"]) != original_len
        if changed:
            self._write_payload(payload)
        return changed

    def add_note(self, task_id: str, content: str) -> Note:
        payload = self.load_payload()
        note = Note(id=str(uuid.uuid4()), task_id=task_id, content=content)
        payload["notes"].append(note.to_dict())

        for task in payload["tasks"]:
            if task.get("id") == task_id:
                refs = task.setdefault("notes_refs", [])
                refs.append(note.id)
                task["updated_at"] = datetime.now().isoformat(timespec="seconds")
                break

        self._write_payload(payload)
        return note

    def list_notes_for_task_on_date(self, task_id: str, day: date) -> list[Note]:
        return [
            note
            for note in self.list_notes()
            if note.task_id == task_id and self._safe_date(note.created_at) == day
        ]

    def increment_focus_time(self, task_id: str, seconds: int) -> bool:
        payload = self.load_payload()
        updated = False
        now = datetime.now().isoformat(timespec="seconds")
        for task in payload["tasks"]:
            if task.get("id") == task_id:
                task["focus_time_spent"] = int(task.get("focus_time_spent", 0)) + seconds
                task["updated_at"] = now
                updated = True
                break

        if updated:
            self._write_payload(payload)
        return updated

    def _write_payload(self, payload: dict) -> None:
        if self.tasks_file.exists():
            self._backup_current_file()

        tmp_path = self.tasks_file.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        tmp_path.replace(self.tasks_file)

    def _backup_current_file(self) -> None:
        self.backup_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.tasks_file, self.backup_file)

    def _restore_from_backup(self) -> bool:
        if not self.backup_file.exists():
            return False
        shutil.copy2(self.backup_file, self.tasks_file)
        return True

    def _normalize_payload(self, payload: dict) -> tuple[dict, bool]:
        changed = False

        if "tasks" not in payload:
            payload["tasks"] = []
            changed = True
        if "notes" not in payload:
            payload["notes"] = []
            changed = True

        for task in payload["tasks"]:
            for key, default in DEFAULT_TASK_FIELDS.items():
                if key not in task:
                    task[key] = list(default) if isinstance(default, list) else dict(default) if isinstance(default, dict) else default
                    changed = True

        return payload, changed

    @staticmethod
    def _safe_date(value: str) -> date | None:
        try:
            return datetime.fromisoformat(value).date()
        except Exception:
            return None
