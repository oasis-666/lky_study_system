from __future__ import annotations

import json
import uuid
from pathlib import Path

from src.models.hardware_log import HardwareLogEntry


class HardwareLogService:
    def __init__(self, storage_file: Path) -> None:
        self.storage_file = storage_file

    def ensure_storage(self) -> None:
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.storage_file.exists():
            self.storage_file.write_text(
                json.dumps({"logs": []}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def list_logs(self) -> list[HardwareLogEntry]:
        self.ensure_storage()
        payload = json.loads(self.storage_file.read_text(encoding="utf-8"))
        return [HardwareLogEntry(**item) for item in payload.get("logs", [])]

    def add_log(self, phenomenon: str, potential_cause: str, solution: str) -> HardwareLogEntry:
        self.ensure_storage()
        payload = json.loads(self.storage_file.read_text(encoding="utf-8"))
        entry = HardwareLogEntry(
            id=str(uuid.uuid4()),
            phenomenon=phenomenon,
            potential_cause=potential_cause,
            solution=solution,
        )
        payload.setdefault("logs", []).append(entry.to_dict())
        self.storage_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return entry
