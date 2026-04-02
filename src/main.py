from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from src.core.config import build_config, load_app_settings
from src.core.countdown_service import CountdownService
from src.core.data_manager import DataManager
from src.core.export_service import ExportService
from src.core.focus_timer import FocusTimerService
from src.core.hardware_log_service import HardwareLogService
from src.core.progress_service import ProgressService
from src.core.quote_engine import QuoteEngine
from src.ui.main_window import MainWindow


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    cfg = build_config(project_root)
    app_settings = load_app_settings(cfg.app_config_file)

    data_manager = DataManager(cfg.tasks_file)
    data_manager.ensure_storage()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = MainWindow(
        data_manager=data_manager,
        progress_service=ProgressService(),
        countdown_service=CountdownService(app_settings["delivery_target_date"]),
        export_service=ExportService(cfg.logs_dir),
        quote_engine=QuoteEngine(cfg.quotes_file),
        focus_timer=FocusTimerService(),
        hardware_log_service=HardwareLogService(cfg.hardware_logs_file),
        app_config_file=cfg.app_config_file,
        app_settings=app_settings,
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
