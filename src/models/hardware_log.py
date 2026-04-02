from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class HardwareLogEntry:
    id: str
    phenomenon: str
    potential_cause: str
    solution: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "phenomenon": self.phenomenon,
            "potential_cause": self.potential_cause,
            "solution": self.solution,
            "created_at": self.created_at,
        }
