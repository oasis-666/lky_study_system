from __future__ import annotations

from datetime import date, datetime, time
import os
import subprocess

from PyQt6.QtCore import QDate, QEasingCurve, QPropertyAnimation, QRect, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QGuiApplication, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSlider,
    QSizePolicy,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.cheatsheet import PYTHON_C_CHEATSHEET
from src.core.config import DEFAULT_CATEGORIES, resolve_resource_path, save_app_settings
from src.core.countdown_service import CountdownService
from src.core.data_manager import DataManager
from src.core.export_service import ExportService
from src.core.focus_timer import FocusTimerService
from src.core.hardware_log_service import HardwareLogService
from src.core.progress_service import ProgressService
from src.core.quote_engine import QuoteEngine
from src.models.task import Task


def _apply_mini_message_box_style(
    msg: QMessageBox,
    danger_confirm: bool = False,
    confirm_button: QPushButton | None = None,
    cancel_button: QPushButton | None = None,
) -> None:
    msg.setObjectName("MiniMessageBox")
    msg.setStyleSheet(
        """
        QMessageBox#MiniMessageBox {
            background-color: rgba(14, 22, 38, 0.98);
            border: 1px solid rgba(116, 174, 255, 0.34);
            border-radius: 16px;
        }
        QMessageBox#MiniMessageBox QLabel {
            color: #EAF3FF;
            font-size: 14px;
            font-weight: 600;
            min-width: 280px;
        }
        QMessageBox#MiniMessageBox QPushButton {
            min-width: 108px;
            min-height: 38px;
            border-radius: 12px;
            border: 1px solid rgba(164, 220, 255, 0.28);
            background-color: rgba(44, 73, 110, 0.85);
            color: #EAF4FF;
            font-weight: 700;
            padding: 8px 16px;
        }
        QMessageBox#MiniMessageBox QPushButton:hover {
            background-color: rgba(66, 106, 154, 0.92);
        }
        QMessageBox#MiniMessageBox QPushButton#ConfirmButton {
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 rgba(0, 183, 255, 0.96),
                stop:1 rgba(0, 121, 255, 0.92));
            color: #051220;
        }
        QMessageBox#MiniMessageBox QPushButton#ConfirmButton:hover {
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 rgba(30, 206, 255, 0.98),
                stop:1 rgba(72, 155, 255, 0.95));
        }
        QMessageBox#MiniMessageBox QPushButton#DangerButton {
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 rgba(239, 68, 68, 0.95),
                stop:1 rgba(220, 38, 38, 0.92));
            color: #FFF5F5;
            border: 1px solid rgba(255, 184, 184, 0.30);
        }
        QMessageBox#MiniMessageBox QPushButton#DangerButton:hover {
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 rgba(248, 113, 113, 0.95),
                stop:1 rgba(220, 38, 38, 0.94));
        }
        QMessageBox#MiniMessageBox QPushButton#CancelButton {
            background-color: rgba(36, 57, 84, 0.78);
            color: #DAECFF;
            border: 1px solid rgba(135, 183, 255, 0.30);
        }
        QMessageBox#MiniMessageBox QPushButton#CancelButton:hover {
            background-color: rgba(54, 82, 121, 0.86);
        }
        """
    )

    if confirm_button is not None:
        confirm_button.setObjectName("DangerButton" if danger_confirm else "ConfirmButton")
    if cancel_button is not None:
        cancel_button.setObjectName("CancelButton")


def show_warning_dialog(parent: QWidget, title: str, text: str) -> None:
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setIcon(QMessageBox.Icon.Warning)
    ok_btn = msg.addButton("知道了", QMessageBox.ButtonRole.AcceptRole)
    _apply_mini_message_box_style(msg, danger_confirm=False, confirm_button=ok_btn)
    msg.setDefaultButton(ok_btn)
    msg.exec()


class TaskDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, task: Task | None = None) -> None:
        super().__init__(parent)
        self._task = task

        self.setObjectName("TaskDialog")
        self.setWindowTitle("新增任务" if task is None else "编辑任务")
        self.setModal(True)
        self.resize(420, 280)

        root = QVBoxLayout(self)
        form = QFormLayout()

        self.name_input = QLineEdit()
        self.category_combo = QComboBox()
        self.category_combo.addItems(DEFAULT_CATEGORIES)

        self.deadline_edit = QDateEdit()
        self.deadline_edit.setCalendarPopup(True)
        self.deadline_edit.setDate(QDate.currentDate())
        self.deadline_edit.setDisplayFormat("yyyy-MM-dd")

        self.weight_combo = QComboBox()
        self.weight_combo.addItems(["Urgent", "Important", "Normal"])

        form.addRow("任务名称", self.name_input)
        form.addRow("分类", self.category_combo)
        form.addRow("截止日期", self.deadline_edit)
        form.addRow("权重", self.weight_combo)
        root.addLayout(form)

        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        actions.addWidget(cancel_btn)

        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._on_save)
        actions.addWidget(save_btn)
        root.addLayout(actions)

        self._load_task()
        self._apply_soft_shadow()

    def _load_task(self) -> None:
        if self._task is None:
            self.category_combo.setCurrentText("STM32")
            self.weight_combo.setCurrentText("Important")
            return

        self.name_input.setText(self._task.task_name)
        self.category_combo.setCurrentText(self._task.category)

        ddl = datetime.strptime(self._task.deadline, "%Y-%m-%d")
        self.deadline_edit.setDate(QDate(ddl.year, ddl.month, ddl.day))

        weight_mapping = {
            "urgent": "Urgent",
            "important": "Important",
            "normal": "Normal",
        }
        self.weight_combo.setCurrentText(weight_mapping.get(self._task.weight, "Normal"))

    def _on_save(self) -> None:
        if not self.name_input.text().strip():
            show_warning_dialog(self, "提示", "任务名称不能为空")
            return
        self.accept()

    def build_payload(self) -> dict:
        weight_mapping = {
            "Urgent": "urgent",
            "Important": "important",
            "Normal": "normal",
        }
        payload = {
            "task_name": self.name_input.text().strip(),
            "category": self.category_combo.currentText(),
            "status": "todo",
            "weight": weight_mapping.get(self.weight_combo.currentText(), "normal"),
            "deadline": self.deadline_edit.date().toString("yyyy-MM-dd"),
            "focus_time_spent": 0,
            "notes_refs": [],
        }

        if self._task is not None:
            payload.update(
                {
                    "id": self._task.id,
                    "status": self._task.status,
                    "focus_time_spent": self._task.focus_time_spent,
                    "notes_refs": self._task.notes_refs,
                    "created_at": self._task.created_at,
                }
            )

        return payload

    def _apply_soft_shadow(self) -> None:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setOffset(0, 8)
        shadow.setBlurRadius(30)
        shadow.setColor(Qt.GlobalColor.black)
        self.setGraphicsEffect(shadow)


class CompletionSummaryDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, draft: str = "") -> None:
        super().__init__(parent)
        self._draft = draft
        self._summary_text: str | None = None

        self.setObjectName("TaskDialog")
        self.setWindowTitle("任务完成总结")
        self.setModal(True)
        self.resize(620, 440)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        title = QLabel("可在模板基础上编辑：")
        title.setStyleSheet("font-weight: 700;")
        root.addWidget(title)

        self.editor = QTextEdit()
        self.editor.setPlaceholderText("写下你的完成总结...")
        self.editor.setPlainText(draft)
        root.addWidget(self.editor, 1)

        self.save_as_note_checkbox = QCheckBox("同时保存为任务笔记")
        self.save_as_note_checkbox.setChecked(True)
        root.addWidget(self.save_as_note_checkbox)

        actions = QHBoxLayout()
        actions.addStretch(1)

        restore_btn = QPushButton("恢复模板")
        restore_btn.clicked.connect(self._restore_draft)
        actions.addWidget(restore_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        actions.addWidget(cancel_btn)

        save_btn = QPushButton("保存总结")
        save_btn.clicked.connect(self._on_save)
        actions.addWidget(save_btn)

        root.addLayout(actions)

    def _restore_draft(self) -> None:
        self.editor.setPlainText(self._draft)

    def _on_save(self) -> None:
        text = self.editor.toPlainText().strip()
        if not text:
            show_warning_dialog(self, "提示", "总结内容不能为空")
            return
        self._summary_text = text
        self.accept()

    def summary_text(self) -> str | None:
        return self._summary_text

    def save_as_note(self) -> bool:
        return self.save_as_note_checkbox.isChecked()


class TaskCardWidget(QFrame):
    selected = pyqtSignal(str)
    completed_toggled = pyqtSignal(str, bool)

    def __init__(self, task: Task, warning_24h: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.task = task
        self.warning_24h = warning_24h
        self._pulse_anim: QPropertyAnimation | None = None

        self.setObjectName("TaskCard")
        self.setProperty("selected", False)
        self.setProperty("warning", warning_24h)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        top_row = QHBoxLayout()
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(task.status == "completed")
        self.checkbox.stateChanged.connect(self._on_checkbox_changed)
        top_row.addWidget(self.checkbox, 0, Qt.AlignmentFlag.AlignTop)

        self.title_label = QLabel(task.task_name)
        self.title_label.setObjectName("TaskTitle")
        self.title_label.setWordWrap(True)
        top_row.addWidget(self.title_label, 1)

        self.deadline_label = QLabel(self._deadline_text(task.deadline))
        self.deadline_label.setObjectName("DeadlineLabel")
        top_row.addWidget(self.deadline_label, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        layout.addLayout(top_row)

        chip_row = QHBoxLayout()
        chip_row.setSpacing(8)

        if task.weight == "urgent":
            chip_row.addWidget(self._build_chip("Urgent", "ChipUrgent"), 0, Qt.AlignmentFlag.AlignLeft)
        elif task.weight == "important":
            chip_row.addWidget(self._build_chip("Important", "ChipImportant"), 0, Qt.AlignmentFlag.AlignLeft)
        else:
            chip_row.addWidget(self._build_chip("Normal", "ChipNormal"), 0, Qt.AlignmentFlag.AlignLeft)

        if warning_24h:
            chip_row.addWidget(self._build_chip("DDL < 24h", "ChipWarn"), 0, Qt.AlignmentFlag.AlignLeft)

        chip_row.addStretch(1)
        layout.addLayout(chip_row)

        self._apply_soft_shadow()
        if warning_24h:
            self._enable_warning_pulse()

    def _build_chip(self, text: str, style_name: str) -> QLabel:
        chip = QLabel(text)
        chip.setObjectName(style_name)
        chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chip.setMinimumWidth(76)
        return chip

    def _deadline_text(self, deadline: str) -> str:
        deadline_dt = datetime.combine(datetime.strptime(deadline, "%Y-%m-%d").date(), time.max)
        now = datetime.now()
        delta_sec = int((deadline_dt - now).total_seconds())
        if delta_sec <= 0:
            return "DDL: 已到期"

        days = delta_sec // 86400
        hours = (delta_sec % 86400) // 3600
        if days > 0:
            return f"DDL: {days}天 {hours}小时"
        return f"DDL: {hours}小时内"

    def _apply_soft_shadow(self) -> None:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setOffset(0, 4)
        shadow.setBlurRadius(18)
        shadow.setColor(QColor(18, 112, 255, 84))
        self.setGraphicsEffect(shadow)

    def _enable_warning_pulse(self) -> None:
        effect = self.graphicsEffect()
        if not isinstance(effect, QGraphicsDropShadowEffect):
            return

        self._pulse_anim = QPropertyAnimation(effect, b"blurRadius", self)
        self._pulse_anim.setStartValue(14)
        self._pulse_anim.setEndValue(28)
        self._pulse_anim.setDuration(1450)
        self._pulse_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._pulse_anim.setLoopCount(-1)
        self._pulse_anim.start()

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        self.selected.emit(self.task.id)
        super().mousePressEvent(event)

    def _on_checkbox_changed(self, state: int) -> None:
        self.completed_toggled.emit(self.task.id, state == int(Qt.CheckState.Checked))


class MainWindow(QMainWindow):
    def __init__(
        self,
        data_manager: DataManager,
        progress_service: ProgressService,
        countdown_service: CountdownService,
        export_service: ExportService,
        quote_engine: QuoteEngine,
        focus_timer: FocusTimerService,
        hardware_log_service: HardwareLogService,
        app_config_file,
        app_settings: dict,
    ) -> None:
        super().__init__()
        self.data_manager = data_manager
        self.progress_service = progress_service
        self.countdown_service = countdown_service
        self.export_service = export_service
        self.quote_engine = quote_engine
        self.focus_timer = focus_timer
        self.hardware_log_service = hardware_log_service
        self.app_config_file = app_config_file
        self.app_settings = app_settings

        self._tasks: list[Task] = []
        self._selected_task_id: str | None = None
        self._card_widgets: dict[str, TaskCardWidget] = {}
        self._progress_anim = QPropertyAnimation()
        self._toast_anim: QPropertyAnimation | None = None
        self._toast_seq = 0
        self._ui_scale = 1.0

        mode_raw = str(app_settings.get("focus_mode", "自由计时"))
        if mode_raw == "正向计时":
            mode_raw = "自由计时"
        self._focus_mode = mode_raw if mode_raw in {"番茄钟", "自由计时"} else "自由计时"
        self._pomodoro_total_seconds = 25 * 60
        self._glass_panel_alpha = self._clamp_alpha(app_settings.get("glass_panel_alpha", 0.93))
        self._glass_card_alpha = self._clamp_alpha(app_settings.get("glass_card_alpha", 0.90))
        self._glass_tab_alpha = self._clamp_alpha(app_settings.get("glass_tab_alpha", 0.84))

        self._focus_session_task_id: str | None = None
        self._focus_started_at: datetime | None = None
        self._focus_elapsed_seconds = 0
        self._focus_running = False
        self._focus_paused = False

        self._bg_pixmap = self._load_background_pixmap()

        self.setWindowTitle("SteadyFocus V2.0")
        self.resize(1320, 820)
        self._build_ui()
        self._apply_theme()
        self._bind_timers()
        self._fit_to_available_screen()
        self._apply_responsive_scale(force=True)
        self.reload_all()

    def _fit_to_available_screen(self) -> None:
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is None:
            return

        available = screen.availableGeometry()
        target_w = min(1320, max(960, int(available.width() * 0.92)))
        target_h = min(860, max(620, int(available.height() * 0.88)))
        target_w = min(target_w, available.width())
        target_h = min(target_h, available.height())

        self.resize(target_w, target_h)
        self.setMinimumSize(900, 600)

        x = available.x() + (available.width() - target_w) // 2
        y = available.y() + (available.height() - target_h) // 2
        self.move(max(available.x(), x), max(available.y(), y))

    def _load_background_pixmap(self) -> QPixmap:
        for path in ("data/bg.jpg", "data/bg.png"):
            pixmap = QPixmap(str(resolve_resource_path(path)))
            if not pixmap.isNull():
                return pixmap
        return QPixmap()

    @staticmethod
    def _clamp_alpha(value, default: float = 0.9) -> float:
        try:
            v = float(value)
        except Exception:
            v = default
        return max(0.5, min(0.98, v))

    def _apply_theme(self) -> None:
        base_font = max(11, int(round(13 * self._ui_scale)))
        timer_font = max(30, int(round(36 * self._ui_scale)))
        button_pad_v = max(8, int(round(10 * self._ui_scale)))
        button_pad_h = max(12, int(round(15 * self._ui_scale)))
        button_min_h = max(38, int(round(42 * self._ui_scale)))

        panel_bg = f"rgba(15, 23, 46, {self._glass_panel_alpha:.2f})"
        card_bg = f"rgba(30, 41, 66, {self._glass_card_alpha:.2f})"
        tab_bg = f"rgba(40, 55, 86, {self._glass_tab_alpha:.2f})"

        self.setStyleSheet(
            """
            QWidget {
                background: transparent;
                color: #F5F8FF;
                font-size: __BASE_FONT__px;
                font-family: "PingFang SC", "Helvetica Neue", "Arial";
            }
            QLabel {
                color: #EAF3FF;
            }
            QListWidget, QTextEdit, QLineEdit, QTableWidget, QScrollArea, QTabWidget::pane {
                background-color: __PANEL_BG__;
                border: 1px solid rgba(124, 170, 255, 0.28);
                border-radius: 16px;
                color: #FFFFFF;
                padding: 6px;
            }
            QTextEdit, QLineEdit {
                selection-background-color: rgba(120, 213, 255, 0.46);
            }
            QTabBar::tab {
                background-color: __TAB_BG__;
                color: #E8F4FF;
                padding: 9px 16px;
                border-radius: 12px;
                margin-right: 6px;
                border: 1px solid rgba(127, 184, 255, 0.24);
            }
            QTabBar::tab:selected {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(0, 212, 255, 0.90),
                    stop:1 rgba(189, 76, 255, 0.92));
                color: #04131F;
                font-weight: 700;
                border: none;
            }
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(0, 183, 255, 0.95),
                    stop:1 rgba(0, 121, 255, 0.92));
                color: #051220;
                border: 1px solid rgba(175, 236, 255, 0.25);
                border-radius: 14px;
                padding: __BTN_PAD_V__px __BTN_PAD_H__px;
                min-height: __BTN_MIN_H__px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(35, 206, 255, 0.98),
                    stop:1 rgba(68, 145, 255, 0.95));
            }
            QPushButton:pressed {
                padding-top: __BTN_PAD_V__px;
                padding-bottom: __BTN_PAD_V__px;
            }
            QPushButton#ExportCTA {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(16, 185, 129, 0.95),
                    stop:1 rgba(56, 239, 125, 0.92));
                color: #032213;
                font-size: 18px;
                font-weight: 800;
                padding: 15px;
                border-radius: 16px;
            }
            QPushButton#CompleteTaskBtn {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(16, 185, 129, 0.95),
                    stop:1 rgba(23, 201, 154, 0.92));
                color: #051B14;
            }
            QPushButton#RestoreTaskBtn {
                background-color: rgba(40, 60, 88, 0.78);
                color: #EAF4FF;
                border: 1px solid rgba(148, 196, 255, 0.35);
            }
            QPushButton#RestoreTaskBtn:hover {
                background-color: rgba(61, 89, 126, 0.88);
            }
            QProgressBar {
                background-color: __PANEL_BG__;
                border: 1px solid rgba(93, 152, 255, 0.30);
                border-radius: 10px;
                text-align: center;
                height: 20px;
                color: #FFFFFF;
            }
            QProgressBar::chunk {
                border-radius: 10px;
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #10B981,
                    stop:1 #34D399);
            }
            QHeaderView::section {
                background-color: rgba(101, 150, 235, 0.18);
                color: #FFFFFF;
                border: none;
                padding: 7px;
            }
            QStatusBar {
                background-color: __PANEL_BG__;
                color: #FFFFFF;
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
            }
            QFrame#TaskCard {
                background-color: __CARD_BG__;
                border: 1px solid rgba(138, 190, 255, 0.24);
                border-radius: 16px;
            }
            QFrame#TaskCard[selected="true"] {
                background-color: rgba(51, 82, 142, 0.90);
                border: 1px solid rgba(121, 207, 255, 0.65);
            }
            QFrame#TaskCard[warning="true"] {
                background-color: rgba(255, 177, 94, 0.30);
                border: 1px solid rgba(255, 201, 129, 0.72);
            }
            QDialog#TaskDialog, QMessageBox {
                background-color: rgba(19, 26, 42, 0.97);
                color: #F1F6FF;
                border-radius: 16px;
                border: 1px solid rgba(125, 177, 255, 0.30);
            }
            QMessageBox QLabel {
                color: #F1F6FF;
            }
            QComboBox {
                background-color: rgba(255, 255, 255, 0.12);
                color: #FFFFFF;
                border: 1px solid rgba(132, 181, 255, 0.24);
                border-radius: 10px;
                padding: 6px 10px;
            }
            QComboBox::drop-down {
                border: none;
                width: 26px;
                background-color: rgba(255, 255, 255, 0.08);
                border-top-right-radius: 10px;
                border-bottom-right-radius: 10px;
            }
            QComboBox QAbstractItemView {
                background-color: rgba(24, 29, 36, 0.98);
                color: #F1F6FF;
                selection-background-color: rgba(0, 163, 255, 0.55);
                selection-color: #FFFFFF;
                border: none;
                border-radius: 10px;
                outline: 0;
            }
            QMenu {
                background-color: rgba(24, 29, 36, 0.98);
                color: #F1F6FF;
                border: none;
                border-radius: 10px;
                padding: 6px;
            }
            QMenu::item:selected {
                background-color: rgba(0, 163, 255, 0.45);
                border-radius: 8px;
            }
            QLabel#TaskTitle {
                font-size: 15px;
                font-weight: 600;
            }
            QLabel#DeadlineLabel {
                color: #E7F2FF;
                font-weight: 600;
            }
            QLabel#ChipUrgent {
                background-color: rgba(215, 44, 44, 0.95);
                color: #FFFFFF;
                border-radius: 10px;
                padding: 3px 10px;
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#ChipImportant {
                background-color: rgba(55, 103, 206, 0.95);
                color: #FFFFFF;
                border-radius: 10px;
                padding: 3px 10px;
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#ChipNormal {
                background-color: rgba(78, 88, 108, 0.88);
                color: #F5F5F5;
                border-radius: 10px;
                padding: 3px 10px;
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#ChipWarn {
                background-color: rgba(217, 119, 6, 0.95);
                color: #FFFFFF;
                border-radius: 10px;
                padding: 3px 10px;
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#ProgressCount {
                color: #F5FBFF;
                font-size: 13px;
                font-weight: 700;
            }
            QFrame#FocusPanel {
                background-color: rgba(18, 30, 51, 0.78);
                border: 1px solid rgba(123, 181, 255, 0.33);
                border-radius: 16px;
            }
            QPushButton#FocusModeButton {
                background-color: rgba(38, 63, 97, 0.72);
                color: #DCEBFF;
                border: 1px solid rgba(136, 191, 255, 0.28);
                min-height: 38px;
            }
            QPushButton#FocusModeButton[selected="true"] {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(0, 212, 255, 0.94),
                    stop:1 rgba(72, 128, 255, 0.92));
                color: #04131F;
                border: 1px solid rgba(192, 243, 255, 0.45);
                font-weight: 800;
            }
            QLabel#FocusTimerDisplay {
                font-size: __TIMER_FONT__px;
                font-weight: 800;
                color: #FFFFFF;
                background-color: rgba(24, 44, 74, 0.74);
                border: 1px solid rgba(112, 188, 255, 0.38);
                border-radius: 14px;
                padding: 10px 14px;
            }
            QPushButton#FocusStartBtn {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(16, 185, 129, 0.95),
                    stop:1 rgba(34, 197, 94, 0.92));
                color: #04160E;
            }
            QPushButton#FocusPauseBtn {
                background-color: rgba(52, 78, 114, 0.84);
                color: #E8F3FF;
                border: 1px solid rgba(145, 194, 255, 0.35);
            }
            QPushButton#FocusPauseBtn:hover {
                background-color: rgba(75, 108, 152, 0.90);
            }
            QPushButton#FocusFinishBtn {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(239, 68, 68, 0.95),
                    stop:1 rgba(220, 38, 38, 0.92));
                color: #FFF5F5;
                border: 1px solid rgba(255, 185, 185, 0.32);
            }
            QPushButton#FocusFinishBtn:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(248, 113, 113, 0.96),
                    stop:1 rgba(220, 38, 38, 0.95));
            }
            QPushButton#GlassActionButton {
                font-size: __BASE_FONT__px;
                min-height: __BTN_MIN_H__px;
                border-radius: 14px;
            }
            QLabel#ToastLabel {
                background-color: rgba(15, 169, 88, 0.98);
                color: #FFFFFF;
                border-radius: 12px;
                padding: 10px 14px;
                font-size: 13px;
                font-weight: 700;
            }
            QFrame#GlassControlPanel {
                background-color: rgba(17, 28, 47, 0.76);
                border: 1px solid rgba(126, 179, 255, 0.28);
                border-radius: 14px;
            }
            """
            .replace("__PANEL_BG__", panel_bg)
            .replace("__CARD_BG__", card_bg)
            .replace("__TAB_BG__", tab_bg)
            .replace("__BASE_FONT__", str(base_font))
            .replace("__TIMER_FONT__", str(timer_font))
            .replace("__BTN_PAD_V__", str(button_pad_v))
            .replace("__BTN_PAD_H__", str(button_pad_h))
            .replace("__BTN_MIN_H__", str(button_min_h))
        )

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(12)

        top_row = QHBoxLayout()
        self.countdown_label = QLabel("距离目标还剩: --")
        self.countdown_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        top_row.addWidget(self.countdown_label, 1)

        self.edit_target_btn = QPushButton("⚙ 编辑目标日")
        self.edit_target_btn.clicked.connect(self.edit_delivery_target)
        top_row.addWidget(self.edit_target_btn, 0, Qt.AlignmentFlag.AlignRight)
        root_layout.addLayout(top_row)

        self.tabs = QTabWidget()
        self.focus_tab = self._build_focus_tab()
        self.knowledge_tab = self._build_knowledge_tab()
        self.tabs.addTab(self.focus_tab, "专注看板")
        self.tabs.addTab(self.knowledge_tab, "知识库")
        root_layout.addWidget(self.tabs, 1)

        self.toast_label = QLabel("", root)
        self.toast_label.setObjectName("ToastLabel")
        self.toast_label.hide()

        status = QStatusBar(self)
        self.status_timer_label = QLabel("今日专注总时长: 00:00:00")
        status.addPermanentWidget(self.status_timer_label)
        self.setStatusBar(status)

        self.setCentralWidget(root)

    def _build_focus_tab(self) -> QWidget:
        tab = QWidget()
        body_layout = QHBoxLayout(tab)
        body_layout.setSpacing(12)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        self.category_list = QListWidget()
        self.category_list.addItem("全部")
        for category in DEFAULT_CATEGORIES:
            self.category_list.addItem(category)
        self.category_list.setCurrentRow(0)
        self.category_list.currentRowChanged.connect(self.reload_task_list)
        left_layout.addWidget(self.category_list, 1)

        self.add_task_btn = QPushButton("+ 新增任务")
        self.add_task_btn.clicked.connect(self.open_add_task_dialog)
        left_layout.addWidget(self.add_task_btn)
        body_layout.addWidget(left_panel, 1)

        center_layout = QVBoxLayout()
        self.current_task_label = QLabel("当前任务: -")
        center_layout.addWidget(self.current_task_label)

        self.summary_title_label = QLabel("完成总结")
        self.summary_title_label.setStyleSheet("font-weight: 700;")
        center_layout.addWidget(self.summary_title_label)

        self.summary_preview = QTextEdit()
        self.summary_preview.setReadOnly(True)
        self.summary_preview.setPlaceholderText("该任务完成后会在这里显示总结")
        self.summary_preview.setMinimumHeight(110)
        self.summary_preview.setMaximumHeight(160)
        center_layout.addWidget(self.summary_preview)

        self.task_scroll = QScrollArea()
        self.task_scroll.setWidgetResizable(True)
        self.task_container = QWidget()
        self.task_cards_layout = QVBoxLayout(self.task_container)
        self.task_cards_layout.setSpacing(10)
        self.task_cards_layout.addStretch(1)
        self.task_scroll.setWidget(self.task_container)
        center_layout.addWidget(self.task_scroll, 1)

        self.progress_label = QLabel("分类进度: -")
        center_layout.addWidget(self.progress_label)

        progress_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        progress_row.addWidget(self.progress_bar, 1)
        self.progress_count_label = QLabel("0/0")
        self.progress_count_label.setObjectName("ProgressCount")
        progress_row.addWidget(self.progress_count_label, 0, Qt.AlignmentFlag.AlignRight)
        center_layout.addLayout(progress_row)

        task_actions = QHBoxLayout()
        self.complete_task_btn = QPushButton("结束任务")
        self.complete_task_btn.setObjectName("CompleteTaskBtn")
        self.complete_task_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.complete_task_btn.clicked.connect(self.complete_selected_task)
        task_actions.addWidget(self.complete_task_btn)

        self.restore_task_btn = QPushButton("恢复未完成")
        self.restore_task_btn.setObjectName("RestoreTaskBtn")
        self.restore_task_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.restore_task_btn.clicked.connect(self.restore_selected_task)
        task_actions.addWidget(self.restore_task_btn)

        self.edit_task_btn = QPushButton("编辑任务")
        self.edit_task_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.edit_task_btn.clicked.connect(self.open_edit_task_dialog)
        task_actions.addWidget(self.edit_task_btn)

        self.delete_task_btn = QPushButton("删除任务")
        self.delete_task_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.delete_task_btn.clicked.connect(self.delete_selected_task)
        task_actions.addWidget(self.delete_task_btn)
        center_layout.addLayout(task_actions)

        body_layout.addLayout(center_layout, 4)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        self.focus_panel = QFrame()
        self.focus_panel.setObjectName("FocusPanel")
        focus_layout = QVBoxLayout(self.focus_panel)
        focus_layout.setContentsMargins(12, 10, 12, 10)
        focus_layout.setSpacing(10)

        mode_row = QVBoxLayout()
        mode_row.setSpacing(8)

        self.mode_pomodoro_btn = QPushButton("🍅 番茄钟 (25分钟)")
        self.mode_pomodoro_btn.setObjectName("FocusModeButton")
        self.mode_pomodoro_btn.clicked.connect(lambda: self._set_focus_mode("番茄钟"))
        mode_row.addWidget(self.mode_pomodoro_btn)

        self.mode_free_btn = QPushButton("⏱️ 自由计时")
        self.mode_free_btn.setObjectName("FocusModeButton")
        self.mode_free_btn.clicked.connect(lambda: self._set_focus_mode("自由计时"))
        mode_row.addWidget(self.mode_free_btn)

        focus_layout.addLayout(mode_row)

        self.focus_time_big_label = QLabel("25:00")
        self.focus_time_big_label.setObjectName("FocusTimerDisplay")
        self.focus_time_big_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        focus_layout.addWidget(self.focus_time_big_label)

        self.focus_start_btn = QPushButton("开始专注")
        self.focus_start_btn.setObjectName("FocusStartBtn")
        self.focus_start_btn.clicked.connect(self.start_focus_session)
        focus_layout.addWidget(self.focus_start_btn)

        self.focus_pause_btn = QPushButton("暂停")
        self.focus_pause_btn.setObjectName("FocusPauseBtn")
        self.focus_pause_btn.clicked.connect(self.pause_focus_session)
        focus_layout.addWidget(self.focus_pause_btn)

        self.focus_finish_btn = QPushButton("结束并结算")
        self.focus_finish_btn.setObjectName("FocusFinishBtn")
        self.focus_finish_btn.clicked.connect(self.finish_focus_session)
        focus_layout.addWidget(self.focus_finish_btn)

        right_layout.addWidget(self.focus_panel)
        right_layout.addStretch(1)
        body_layout.addWidget(right_panel, 2)

        self._update_focus_mode_buttons()
        self._update_focus_controls()
        return tab

    def _build_knowledge_tab(self) -> QWidget:
        tab_content = QWidget()
        layout = QVBoxLayout(tab_content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(16)

        glass_panel = QFrame()
        glass_panel.setObjectName("GlassControlPanel")
        glass_layout = QVBoxLayout(glass_panel)
        glass_layout.setContentsMargins(10, 10, 10, 10)
        glass_layout.setSpacing(8)

        glass_title = QLabel("界面透明度")
        glass_title.setStyleSheet("font-weight: 700;")
        glass_layout.addWidget(glass_title)

        self.panel_alpha_label = QLabel()
        self.panel_alpha_slider = QSlider(Qt.Orientation.Horizontal)
        self.panel_alpha_slider.setRange(50, 98)
        self.panel_alpha_slider.setValue(int(self._glass_panel_alpha * 100))
        self.panel_alpha_slider.valueChanged.connect(self.on_glass_slider_changed)
        glass_layout.addWidget(self.panel_alpha_label)
        glass_layout.addWidget(self.panel_alpha_slider)

        self.card_alpha_label = QLabel()
        self.card_alpha_slider = QSlider(Qt.Orientation.Horizontal)
        self.card_alpha_slider.setRange(50, 98)
        self.card_alpha_slider.setValue(int(self._glass_card_alpha * 100))
        self.card_alpha_slider.valueChanged.connect(self.on_glass_slider_changed)
        glass_layout.addWidget(self.card_alpha_label)
        glass_layout.addWidget(self.card_alpha_slider)

        self.tab_alpha_label = QLabel()
        self.tab_alpha_slider = QSlider(Qt.Orientation.Horizontal)
        self.tab_alpha_slider.setRange(50, 98)
        self.tab_alpha_slider.setValue(int(self._glass_tab_alpha * 100))
        self.tab_alpha_slider.valueChanged.connect(self.on_glass_slider_changed)
        glass_layout.addWidget(self.tab_alpha_label)
        glass_layout.addWidget(self.tab_alpha_slider)

        glass_actions = QHBoxLayout()
        glass_actions.setSpacing(12)
        self.save_glass_btn = QPushButton("保存透明度")
        self.save_glass_btn.setObjectName("GlassActionButton")
        self.save_glass_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.save_glass_btn.clicked.connect(self.save_glass_settings)
        glass_actions.addWidget(self.save_glass_btn)

        self.reset_glass_btn = QPushButton("恢复默认")
        self.reset_glass_btn.setObjectName("GlassActionButton")
        self.reset_glass_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.reset_glass_btn.clicked.connect(self.reset_glass_settings)
        glass_actions.addWidget(self.reset_glass_btn)
        glass_layout.addLayout(glass_actions)

        self._update_glass_labels()
        layout.addWidget(glass_panel)
        layout.addSpacing(4)

        self.quote_label = QLabel("激励语加载中...")
        self.quote_label.setWordWrap(True)
        layout.addWidget(self.quote_label)

        self.note_input = QTextEdit()
        self.note_input.setPlaceholderText("记录 Markdown 笔记...")
        layout.addWidget(self.note_input)

        note_actions = QHBoxLayout()
        self.add_note_btn = QPushButton("添加笔记到当前任务")
        self.add_note_btn.clicked.connect(self.add_note_to_selected_task)
        note_actions.addWidget(self.add_note_btn)

        self.cheatsheet_btn = QPushButton("打开 Python-C 对照")
        self.cheatsheet_btn.clicked.connect(self.show_cheatsheet)
        note_actions.addWidget(self.cheatsheet_btn)
        layout.addLayout(note_actions)
        layout.addSpacing(4)

        self.hw_ph_input = QLineEdit()
        self.hw_ph_input.setPlaceholderText("Phenomenon")
        layout.addWidget(self.hw_ph_input)
        self.hw_cause_input = QLineEdit()
        self.hw_cause_input.setPlaceholderText("Potential Cause")
        layout.addWidget(self.hw_cause_input)
        self.hw_solution_input = QLineEdit()
        self.hw_solution_input.setPlaceholderText("Solution")
        layout.addWidget(self.hw_solution_input)

        self.add_hw_btn = QPushButton("新增 Hardware Log")
        self.add_hw_btn.clicked.connect(self.add_hardware_log)
        layout.addWidget(self.add_hw_btn)
        layout.addSpacing(2)

        self.hw_table = QTableWidget(0, 3)
        self.hw_table.setHorizontalHeaderLabels(["Phenomenon", "Potential Cause", "Solution"])
        self.hw_table.setAlternatingRowColors(True)
        layout.addWidget(self.hw_table, 1)
        layout.addSpacing(4)

        self.export_btn = QPushButton("生成 Obsidian 日报")
        self.export_btn.setObjectName("ExportCTA")
        self.export_btn.clicked.connect(self.export_today_log)
        layout.addWidget(self.export_btn, 0, Qt.AlignmentFlag.AlignRight)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(tab_content)

        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(scroll)
        return tab

    def _bind_timers(self) -> None:
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self.update_countdown)
        self.countdown_timer.start(1000)

        self.focus_status_timer = QTimer(self)
        self.focus_status_timer.timeout.connect(self.update_focus_status)
        self.focus_status_timer.start(1000)

        self.quote_timer = QTimer(self)
        self.quote_timer.timeout.connect(self.update_quote)
        self.quote_timer.start(3600 * 1000)

    def _update_glass_labels(self) -> None:
        self.panel_alpha_label.setText(f"面板透明度: {self._glass_panel_alpha:.2f}")
        self.card_alpha_label.setText(f"任务卡透明度: {self._glass_card_alpha:.2f}")
        self.tab_alpha_label.setText(f"Tab 透明度: {self._glass_tab_alpha:.2f}")

    def on_glass_slider_changed(self) -> None:
        self._glass_panel_alpha = self.panel_alpha_slider.value() / 100
        self._glass_card_alpha = self.card_alpha_slider.value() / 100
        self._glass_tab_alpha = self.tab_alpha_slider.value() / 100
        self._update_glass_labels()
        self._apply_theme()

    def save_glass_settings(self) -> None:
        self.app_settings["glass_panel_alpha"] = round(self._glass_panel_alpha, 2)
        self.app_settings["glass_card_alpha"] = round(self._glass_card_alpha, 2)
        self.app_settings["glass_tab_alpha"] = round(self._glass_tab_alpha, 2)
        save_app_settings(self.app_config_file, self.app_settings)
        self._show_toast("透明度配置已保存")

    def reset_glass_settings(self) -> None:
        self._glass_panel_alpha = 0.93
        self._glass_card_alpha = 0.90
        self._glass_tab_alpha = 0.84
        self.panel_alpha_slider.setValue(int(self._glass_panel_alpha * 100))
        self.card_alpha_slider.setValue(int(self._glass_card_alpha * 100))
        self.tab_alpha_slider.setValue(int(self._glass_tab_alpha * 100))
        self._update_glass_labels()
        self._apply_theme()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        if not self._bg_pixmap.isNull():
            target = self.rect()
            source = self._cover_source_rect(self._bg_pixmap, target)
            painter.drawPixmap(target, self._bg_pixmap, source)
        else:
            painter.fillRect(self.rect(), Qt.GlobalColor.black)
        super().paintEvent(event)

    def _cover_source_rect(self, pixmap: QPixmap, target: QRect) -> QRect:
        pw, ph = pixmap.width(), pixmap.height()
        tw, th = max(1, target.width()), max(1, target.height())
        if pw <= 0 or ph <= 0:
            return QRect(0, 0, 1, 1)

        scale = max(tw / pw, th / ph)
        sw = int(tw / scale)
        sh = int(th / scale)
        sx = max(0, (pw - sw) // 2)
        sy = max(0, (ph - sh) // 2)
        return QRect(sx, sy, sw, sh)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._apply_responsive_scale()
        if self.toast_label.isVisible():
            self._position_toast()

    def _apply_responsive_scale(self, force: bool = False) -> None:
        width_ratio = self.width() / 1320
        height_ratio = self.height() / 820
        target_scale = max(0.72, min(1.30, width_ratio * 0.45 + height_ratio * 0.55))
        if not force and abs(target_scale - self._ui_scale) < 0.03:
            return

        self._ui_scale = target_scale
        self.countdown_label.setStyleSheet(
            f"font-size: {max(18, int(round(24 * self._ui_scale)))}px; font-weight: bold;"
        )
        btn_h = max(32, int(round(40 * self._ui_scale)))
        self.save_glass_btn.setMinimumHeight(btn_h)
        self.reset_glass_btn.setMinimumHeight(btn_h)
        self.focus_start_btn.setMinimumHeight(btn_h)
        self.focus_pause_btn.setMinimumHeight(btn_h)
        self.focus_finish_btn.setMinimumHeight(btn_h)

        preview_h = max(84, int(round(160 * self._ui_scale)))
        self.summary_preview.setMaximumHeight(preview_h)
        self.summary_preview.setMinimumHeight(max(70, int(round(96 * self._ui_scale))))

        self._apply_theme()

    def reload_all(self) -> None:
        self.reload_task_list()
        self.refresh_hardware_logs()
        self.update_countdown()
        self.update_quote()
        self.update_focus_status()

    def _clear_task_cards(self) -> None:
        while self.task_cards_layout.count() > 1:
            item = self.task_cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._card_widgets.clear()

    def reload_task_list(self) -> None:
        tasks = self.data_manager.list_tasks()
        tasks = self.progress_service.sort_tasks(tasks)

        selected_category = self.category_list.currentItem().text() if self.category_list.currentItem() else "全部"
        if selected_category != "全部":
            tasks = [t for t in tasks if t.category == selected_category]

        self._tasks = tasks
        if self._selected_task_id and not any(t.id == self._selected_task_id for t in tasks):
            self._selected_task_id = None

        self._clear_task_cards()
        for task in tasks:
            warning = self.progress_service.is_deadline_within_24h(task)
            card = TaskCardWidget(task, warning, self.task_container)
            card.selected.connect(self.on_card_selected)
            card.completed_toggled.connect(self.on_card_completed_toggled)
            self.task_cards_layout.insertWidget(self.task_cards_layout.count() - 1, card)
            self._card_widgets[task.id] = card

        if tasks and self._selected_task_id is None:
            self._selected_task_id = tasks[0].id

        self._sync_selected_card_state()
        self.on_task_selected()
        self.refresh_progress()

    def _sync_selected_card_state(self) -> None:
        for task_id, card in self._card_widgets.items():
            card.set_selected(task_id == self._selected_task_id)

    def on_card_selected(self, task_id: str) -> None:
        self._selected_task_id = task_id
        self._sync_selected_card_state()
        self.on_task_selected()

    def on_card_completed_toggled(self, task_id: str, completed: bool) -> None:
        task = next((t for t in self._tasks if t.id == task_id), None)
        if task is None:
            return

        payload = task.to_dict()
        payload["status"] = "completed" if completed else "todo"

        if completed and task.status != "completed":
            payload["completed_at"] = datetime.now().isoformat(timespec="seconds")

            completion_meta = dict(payload.get("completion_meta") or {})
            elapsed = self._flush_focus_time_for_task(task.id)
            if elapsed > 0:
                completion_meta["focus_auto_added_seconds"] = elapsed

            draft = self._build_completion_draft(task.id)
            summary, save_as_note = self._ask_completion_summary(draft)
            if summary is not None and summary.strip():
                payload["completion_summary"] = summary.strip()
                if save_as_note:
                    self.data_manager.add_note(task.id, f"[完成总结]\n{summary.strip()}")

            archive_candidate = self._ask_archive_candidate()
            completion_meta["archive_candidate"] = archive_candidate
            payload["completion_meta"] = completion_meta

        if not completed:
            payload["completed_at"] = ""
            payload["completion_summary"] = ""
            completion_meta = dict(payload.get("completion_meta") or {})
            completion_meta["archive_candidate"] = False
            payload["completion_meta"] = completion_meta

        self._selected_task_id = task.id
        self.data_manager.upsert_task(payload)
        self.reload_task_list()

        if completed:
            toast_msg = "任务已完成"
            if payload.get("completion_summary"):
                toast_msg += "，总结已保存"
            self._show_toast(toast_msg)
        else:
            self._show_toast("任务已恢复为未完成")

    def open_add_task_dialog(self) -> None:
        dialog = TaskDialog(self)
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return

        saved = self.data_manager.upsert_task(dialog.build_payload())
        self._selected_task_id = saved.id
        self.reload_task_list()
        self._show_toast("任务已新增")

    def complete_selected_task(self) -> None:
        task = self.get_selected_task()
        if task is None:
            show_warning_dialog(self, "提示", "请先选择任务")
            return
        if task.status == "completed":
            self._show_toast("任务已是完成状态")
            return
        self.on_card_completed_toggled(task.id, True)

    def restore_selected_task(self) -> None:
        task = self.get_selected_task()
        if task is None:
            show_warning_dialog(self, "提示", "请先选择任务")
            return
        if task.status != "completed":
            self._show_toast("任务当前不是完成状态")
            return
        self.on_card_completed_toggled(task.id, False)

    def open_edit_task_dialog(self) -> None:
        task = self.get_selected_task()
        if task is None:
            show_warning_dialog(self, "提示", "请先选择任务")
            return

        dialog = TaskDialog(self, task)
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return

        saved = self.data_manager.upsert_task(dialog.build_payload())
        self._selected_task_id = saved.id
        self.reload_task_list()
        self._show_toast("任务已更新")

    def delete_selected_task(self) -> None:
        task = self.get_selected_task()
        if task is None:
            show_warning_dialog(self, "提示", "请先选择任务")
            return

        confirm = self._ask_confirm(
            "确认删除",
            f"确定删除任务：{task.task_name}？",
            confirm_text="删除",
            cancel_text="取消",
            default_confirm=False,
            danger_confirm=True,
        )
        if not confirm:
            return

        self.data_manager.delete_task(task.id)
        self._selected_task_id = None
        self.reload_task_list()
        self._show_toast("任务已删除")

    def refresh_progress(self) -> None:
        all_tasks = self.data_manager.list_tasks()
        by_category = self.progress_service.compute_by_category(all_tasks)

        current_category = self.category_list.currentItem().text() if self.category_list.currentItem() else "全部"
        if current_category == "全部":
            total = sum(v["total"] for v in by_category.values())
            completed = sum(v["completed"] for v in by_category.values())
            rate = round((completed / total * 100) if total else 0.0, 2)
            self.progress_label.setText(f"总进度: {completed}/{total} ({rate}%)")
            self.progress_count_label.setText(f"{completed}/{total}")
            self._animate_progress_to(int(rate))
            return

        slot = by_category.get(current_category, {"total": 0, "completed": 0, "completion_rate": 0.0})
        self.progress_label.setText(
            f"{current_category} 进度: {slot['completed']}/{slot['total']} ({slot['completion_rate']}%)"
        )
        self.progress_count_label.setText(f"{slot['completed']}/{slot['total']}")
        self._animate_progress_to(int(slot["completion_rate"]))

    def _animate_progress_to(self, value: int) -> None:
        value = max(0, min(100, value))
        start_value = self.progress_bar.value()
        if start_value == value:
            return

        self._progress_anim.stop()
        self._progress_anim = QPropertyAnimation(self.progress_bar, b"value", self)
        self._progress_anim.setDuration(460)
        self._progress_anim.setStartValue(start_value)
        self._progress_anim.setEndValue(value)
        self._progress_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._progress_anim.start()

    def on_task_selected(self) -> None:
        task = self.get_selected_task()
        if task is None:
            self.current_task_label.setText("当前任务: -")
            self.summary_preview.setPlainText("")
            self.complete_task_btn.setEnabled(False)
            self.restore_task_btn.setEnabled(False)
            self._update_focus_controls()
            return

        is_done = task.status == "completed"
        self.complete_task_btn.setEnabled(not is_done)
        self.restore_task_btn.setEnabled(is_done)

        self.current_task_label.setText(f"当前任务: {task.task_name} | 权重: {task.weight} | DDL: {task.deadline}")

        lines: list[str] = []
        if task.completed_at:
            lines.append(f"完成时间: {task.completed_at}")
        if task.completion_summary.strip():
            lines.append("")
            lines.append(task.completion_summary.strip())

        self.summary_preview.setPlainText("\n".join(lines))
        self._update_focus_controls()

    def get_selected_task(self) -> Task | None:
        if self._selected_task_id is None:
            return None
        for task in self._tasks:
            if task.id == self._selected_task_id:
                return task
        return None

    def _set_focus_mode(self, mode: str) -> None:
        if mode not in {"番茄钟", "自由计时"}:
            return
        if self._focus_running or self._focus_paused:
            show_warning_dialog(self, "提示", "请先结束并结算当前专注，再切换模式")
            return

        self._focus_mode = mode
        self.app_settings["focus_mode"] = mode
        save_app_settings(self.app_config_file, self.app_settings)
        self._update_focus_mode_buttons()
        self._update_focus_controls()
        self.update_focus_status()

    def _update_focus_mode_buttons(self) -> None:
        self.mode_pomodoro_btn.setProperty("selected", self._focus_mode == "番茄钟")
        self.mode_free_btn.setProperty("selected", self._focus_mode == "自由计时")
        for btn in (self.mode_pomodoro_btn, self.mode_free_btn):
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.update()

    def _current_session_seconds(self) -> int:
        seconds = self._focus_elapsed_seconds
        if self._focus_running and self._focus_started_at is not None:
            seconds += int((datetime.now() - self._focus_started_at).total_seconds())
        return max(0, seconds)

    def _update_focus_controls(self) -> None:
        task_selected = self.get_selected_task() is not None
        has_session = self._focus_session_task_id is not None and self._current_session_seconds() > 0

        self.focus_start_btn.setEnabled(task_selected and not self._focus_running)
        self.focus_pause_btn.setEnabled(self._focus_running)
        self.focus_finish_btn.setEnabled(self._focus_running or has_session or self._focus_paused)

        if self._focus_paused:
            self.focus_start_btn.setText("继续专注")
        else:
            self.focus_start_btn.setText("开始专注")

    def start_focus_session(self) -> None:
        task = self.get_selected_task()
        if task is None:
            show_warning_dialog(self, "提示", "请先选择任务")
            return

        if self._focus_session_task_id and self._focus_session_task_id != task.id:
            show_warning_dialog(self, "提示", "当前已有其他任务的专注会话，请先结束并结算")
            return

        if self._focus_running:
            return

        if self._focus_session_task_id is None:
            self._focus_session_task_id = task.id
            self._focus_elapsed_seconds = 0

        active = self.focus_timer.active_task_id()
        if active is None:
            self.focus_timer.start(task.id)
        elif active == task.id and not self.focus_timer.is_running():
            self.focus_timer.resume()

        self._focus_started_at = datetime.now()
        self._focus_running = True
        self._focus_paused = False
        self._update_focus_controls()
        self.update_focus_status()

    def pause_focus_session(self) -> None:
        if not self._focus_running:
            return

        if self._focus_started_at is not None:
            self._focus_elapsed_seconds += int((datetime.now() - self._focus_started_at).total_seconds())
        self._focus_started_at = None
        self._focus_running = False
        self._focus_paused = True

        self.focus_timer.pause()
        self._update_focus_controls()
        self.update_focus_status()

    def finish_focus_session(self) -> int:
        return self._finish_focus_session(auto_complete=False)

    def _finish_focus_session(self, auto_complete: bool) -> int:
        if self._focus_session_task_id is None:
            return 0

        if self._focus_running and self._focus_started_at is not None:
            self._focus_elapsed_seconds += int((datetime.now() - self._focus_started_at).total_seconds())
            self.focus_timer.pause()

        seconds = max(0, self._focus_elapsed_seconds)
        task_id = self._focus_session_task_id
        if seconds > 0:
            self.data_manager.increment_focus_time(task_id, seconds)
            self.refresh_progress()

        self.focus_timer.stop()
        self._focus_session_task_id = None
        self._focus_started_at = None
        self._focus_elapsed_seconds = 0
        self._focus_running = False
        self._focus_paused = False

        self._update_focus_controls()
        self.update_focus_status()

        if seconds > 0 and not auto_complete:
            self._show_toast(f"已结算专注 {seconds} 秒")
        return seconds

    def update_focus_status(self) -> None:
        today_total = self.focus_timer.today_seconds()
        hh = today_total // 3600
        mm = (today_total % 3600) // 60
        ss = today_total % 60
        self.status_timer_label.setText(f"今日专注总时长: {hh:02d}:{mm:02d}:{ss:02d}")

        session_seconds = self._current_session_seconds()
        if self._focus_mode == "番茄钟":
            remaining = max(0, self._pomodoro_total_seconds - session_seconds)
            self.focus_time_big_label.setText(f"{remaining // 60:02d}:{remaining % 60:02d}")
            if self._focus_running and remaining <= 0:
                self._finish_focus_session(auto_complete=True)
                self._show_toast("番茄钟完成！")
            return

        hh2 = session_seconds // 3600
        mm2 = (session_seconds % 3600) // 60
        ss2 = session_seconds % 60
        self.focus_time_big_label.setText(f"{hh2:02d}:{mm2:02d}:{ss2:02d}")

    def update_countdown(self) -> None:
        remaining = self.countdown_service.get_remaining()
        if remaining["expired"]:
            self.countdown_label.setText("已到目标日期")
            return
        self.countdown_label.setText(
            "距离目标日: "
            f"{remaining['days']}天 {remaining['hours']:02d}:{remaining['minutes']:02d}:{remaining['seconds']:02d}"
        )

    def edit_delivery_target(self) -> None:
        dialog = QDialog(self)
        dialog.setObjectName("TaskDialog")
        dialog.setWindowTitle("编辑目标日期")
        dialog.resize(320, 160)

        root = QVBoxLayout(dialog)
        form = QFormLayout()
        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        date_edit.setDisplayFormat("yyyy-MM-dd")

        current = str(self.app_settings.get("delivery_target_date", "2026-04-20"))
        dt = datetime.strptime(current, "%Y-%m-%d")
        date_edit.setDate(QDate(dt.year, dt.month, dt.day))
        form.addRow("目标日期", date_edit)
        root.addLayout(form)

        row = QHBoxLayout()
        row.addStretch(1)
        ok_btn = QPushButton("保存")
        cancel_btn = QPushButton("取消")
        row.addWidget(cancel_btn)
        row.addWidget(ok_btn)
        root.addLayout(row)

        cancel_btn.clicked.connect(dialog.reject)

        def commit() -> None:
            new_date = date_edit.date().toString("yyyy-MM-dd")
            self.app_settings["delivery_target_date"] = new_date
            save_app_settings(self.app_config_file, self.app_settings)
            self.countdown_service = CountdownService(new_date)
            self.update_countdown()
            dialog.accept()
            self._show_toast("目标日已更新")

        ok_btn.clicked.connect(commit)
        dialog.exec()

    def update_quote(self) -> None:
        self.quote_label.setText(self.quote_engine.next_quote())

    def add_note_to_selected_task(self) -> None:
        task = self.get_selected_task()
        content = self.note_input.toPlainText().strip()
        if task is None:
            show_warning_dialog(self, "提示", "请先选择任务")
            return
        if not content:
            show_warning_dialog(self, "提示", "请输入笔记内容")
            return

        self.data_manager.add_note(task.id, content)
        self.note_input.clear()
        self._show_toast("笔记已写入任务")

    def _build_completion_draft(self, task_id: str) -> str:
        notes = self.data_manager.list_notes_for_task_on_date(task_id, date.today())

        lines = [
            "完成了什么：",
            "",
            "遇到的问题：",
            "",
            "下一步：",
            "",
        ]

        if notes:
            lines.append("今日笔记回顾：")
            for note in notes:
                hhmm = note.created_at[11:16] if len(note.created_at) >= 16 else "--:--"
                lines.append(f"- [{hhmm}] {note.content}")

        return "\n".join(lines).strip()

    def _ask_completion_summary(self, draft: str) -> tuple[str | None, bool]:
        should_fill = self._ask_confirm(
            "完成总结",
            "任务已完成，是否现在填写总结？",
            confirm_text="填写",
            cancel_text="跳过",
            default_confirm=True,
            danger_confirm=False,
        )
        if not should_fill:
            return None, False

        dialog = CompletionSummaryDialog(self, draft)
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return None, False
        return dialog.summary_text(), dialog.save_as_note()

    def _ask_archive_candidate(self) -> bool:
        return self._ask_confirm(
            "归档提醒",
            "该任务已完成，是否标记为归档候选？",
            confirm_text="标记",
            cancel_text="暂不",
            default_confirm=False,
            danger_confirm=False,
        )

    def _ask_confirm(
        self,
        title: str,
        text: str,
        confirm_text: str = "是",
        cancel_text: str = "否",
        default_confirm: bool = False,
        danger_confirm: bool = False,
    ) -> bool:
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setIcon(QMessageBox.Icon.Question)

        confirm_btn = msg.addButton(confirm_text, QMessageBox.ButtonRole.YesRole)
        cancel_btn = msg.addButton(cancel_text, QMessageBox.ButtonRole.NoRole)
        _apply_mini_message_box_style(
            msg,
            danger_confirm=danger_confirm,
            confirm_button=confirm_btn,
            cancel_button=cancel_btn,
        )
        msg.setDefaultButton(confirm_btn if default_confirm else cancel_btn)

        msg.exec()
        return msg.clickedButton() == confirm_btn

    def _ask_yes_no(self, title: str, text: str, default_yes: bool = False) -> bool:
        return self._ask_confirm(
            title,
            text,
            confirm_text="是",
            cancel_text="否",
            default_confirm=default_yes,
            danger_confirm=False,
        )

    def _flush_focus_time_for_task(self, task_id: str) -> int:
        if self._focus_session_task_id != task_id:
            return 0
        return self._finish_focus_session(auto_complete=False)

    def export_today_log(self) -> None:
        today = date.today().isoformat()
        output = self.export_service.export_daily_markdown(
            today,
            self.data_manager.list_tasks(),
            self.data_manager.list_notes(),
        )
        self._show_toast("日报打包成功", success=True)
        self._open_logs_folder(output.parent)

    def _open_logs_folder(self, logs_dir) -> None:
        dir_path = str(logs_dir)
        try:
            if os.name == "nt":
                os.startfile(dir_path)  # type: ignore[attr-defined]
            elif os.name == "posix" and "darwin" in os.sys.platform:
                subprocess.call(["open", dir_path])
            else:
                subprocess.call(["xdg-open", dir_path])
        except Exception:
            self._show_toast("导出成功，但打开目录失败", success=False)

    def show_cheatsheet(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Python-C 语法对照")
        dialog.resize(680, 420)
        dialog.setObjectName("TaskDialog")

        layout = QVBoxLayout(dialog)
        viewer = QTextEdit(dialog)
        viewer.setReadOnly(True)
        viewer.setStyleSheet("QTextEdit { background-color: rgba(255,255,255,0.10); border: none; border-radius: 12px; }")

        lines = ["# Python -> C 对照\n"]
        for py, c in PYTHON_C_CHEATSHEET:
            lines.append(f"Python : {py}\nC      : {c}\n")
        viewer.setPlainText("\n".join(lines))
        layout.addWidget(viewer)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignRight)

        dialog.exec()

    def add_hardware_log(self) -> None:
        ph = self.hw_ph_input.text().strip()
        cause = self.hw_cause_input.text().strip()
        solution = self.hw_solution_input.text().strip()
        if not ph or not cause or not solution:
            show_warning_dialog(self, "提示", "请完整填写 Hardware Log 字段")
            return

        self.hardware_log_service.add_log(ph, cause, solution)
        self.hw_ph_input.clear()
        self.hw_cause_input.clear()
        self.hw_solution_input.clear()
        self.refresh_hardware_logs()
        self._show_toast("Hardware Log 已记录")

    def refresh_hardware_logs(self) -> None:
        logs = self.hardware_log_service.list_logs()
        self.hw_table.setRowCount(len(logs))
        for row, item in enumerate(logs):
            self.hw_table.setItem(row, 0, QTableWidgetItem(item.phenomenon))
            self.hw_table.setItem(row, 1, QTableWidgetItem(item.potential_cause))
            self.hw_table.setItem(row, 2, QTableWidgetItem(item.solution))

    def _position_toast(self) -> None:
        root = self.centralWidget()
        if root is None:
            return
        self.toast_label.adjustSize()
        x = root.width() - self.toast_label.width() - 24
        y = root.height() - self.toast_label.height() - 24
        self.toast_label.move(max(8, x), max(8, y))

    def _show_toast(self, message: str, success: bool = True) -> None:
        self._toast_seq += 1
        current_seq = self._toast_seq

        self.toast_label.setText(message)
        if success:
            self.toast_label.setStyleSheet(
                "QLabel#ToastLabel { background-color: rgba(15, 169, 88, 0.98); color: #FFFFFF; border-radius: 12px; padding: 10px 14px; font-size: 13px; font-weight: 700; }"
            )
        else:
            self.toast_label.setStyleSheet(
                "QLabel#ToastLabel { background-color: rgba(194, 77, 77, 0.98); color: #FFFFFF; border-radius: 12px; padding: 10px 14px; font-size: 13px; font-weight: 700; }"
            )

        self._position_toast()
        self.toast_label.show()

        if self._toast_anim is not None:
            self._toast_anim.stop()

        effect = QGraphicsOpacityEffect(self.toast_label)
        self.toast_label.setGraphicsEffect(effect)
        effect.setOpacity(0.0)

        self._toast_anim = QPropertyAnimation(effect, b"opacity", self)
        self._toast_anim.setDuration(280)
        self._toast_anim.setStartValue(0.0)
        self._toast_anim.setEndValue(1.0)
        self._toast_anim.start()

        def fade_out() -> None:
            if current_seq != self._toast_seq:
                return

            current_effect = self.toast_label.graphicsEffect()
            if not isinstance(current_effect, QGraphicsOpacityEffect):
                self.toast_label.hide()
                return

            fade_anim = QPropertyAnimation(current_effect, b"opacity", self)
            fade_anim.setDuration(380)
            fade_anim.setStartValue(1.0)
            fade_anim.setEndValue(0.0)

            def cleanup() -> None:
                if current_seq != self._toast_seq:
                    return
                self.toast_label.hide()
                self.toast_label.setGraphicsEffect(None)

            fade_anim.finished.connect(cleanup)
            fade_anim.start()
            self._toast_anim = fade_anim

        QTimer.singleShot(1250, fade_out)
