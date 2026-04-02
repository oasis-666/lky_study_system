from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sys


@dataclass(frozen=True)
class AppConfig:
    project_root: Path
    data_dir: Path
    logs_dir: Path
    tasks_file: Path
    quotes_file: Path
    hardware_logs_file: Path
    bg_file: Path
    app_config_file: Path


DEFAULT_CATEGORIES = ["STM32", "高数", "剧本", "PID"]
DELIVERY_DATE = "2026-04-20"
DEFAULT_APP_SETTINGS = {
    "delivery_target_date": DELIVERY_DATE,
    "focus_mode": "正向计时",
    "pomodoro_minutes_options": [15, 25, 50],
    "pomodoro_minutes_default": 25,
    "glass_panel_alpha": 0.93,
    "glass_card_alpha": 0.90,
    "glass_tab_alpha": 0.84,
}


def build_config(project_root: Path) -> AppConfig:
    data_dir = project_root / "data"
    logs_dir = data_dir / "logs"
    bg_jpg = data_dir / "bg.jpg"
    bg_png = data_dir / "bg.png"
    bg_file = bg_jpg if bg_jpg.exists() else bg_png
    return AppConfig(
        project_root=project_root,
        data_dir=data_dir,
        logs_dir=logs_dir,
        tasks_file=data_dir / "tasks.json",
        quotes_file=data_dir / "quotes.json",
        hardware_logs_file=data_dir / "hardware_logs.json",
        bg_file=bg_file,
        app_config_file=data_dir / "config.json",
    )


def resolve_resource_path(relative_path: str) -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return (Path(bundle_root) / relative_path).resolve()
    return (Path(__file__).resolve().parents[2] / relative_path).resolve()


def load_app_settings(config_file: Path) -> dict:
    config_file.parent.mkdir(parents=True, exist_ok=True)
    if not config_file.exists():
        save_app_settings(config_file, DEFAULT_APP_SETTINGS)
        return dict(DEFAULT_APP_SETTINGS)

    try:
        data = json.loads(config_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("config root must be object")
    except Exception:
        save_app_settings(config_file, DEFAULT_APP_SETTINGS)
        return dict(DEFAULT_APP_SETTINGS)

    merged = dict(DEFAULT_APP_SETTINGS)
    merged.update(data)
    return merged


def save_app_settings(config_file: Path, settings: dict) -> None:
    config_file.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(DEFAULT_APP_SETTINGS)
    payload.update(settings)
    config_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
