"""Main application window with tabs, menu bar, status bar, and system tray."""

import os
from datetime import datetime
from typing import Any

from PyQt6.QtWidgets import (
    QDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSystemTrayIcon,
    QTabWidget,
    QApplication,
)

from app.gui.config_dialog import ConfigDialog
from app.config_manager import get_config
from app.event_bus import EventBus, ProcessingEvent
from app.gui.dashboard_widget import DashboardWidget
from app.gui.log_widget import LogWidget
from app.gui.resources import get_app_icon
from app.gui.tray_icon import TrayIcon


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self, event_bus: EventBus):
        super().__init__()
        self.event_bus = event_bus

        self.setWindowTitle("PDF Uploader")
        self.setWindowIcon(get_app_icon())
        self.setMinimumSize(900, 600)

        # Central widget with tabs
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Dashboard tab
        self.dashboard = DashboardWidget()
        self.tabs.addTab(self.dashboard, "Dashboard")

        # Log tab
        self.log_widget = LogWidget()
        self.tabs.addTab(self.log_widget, "Log")

        # Menu bar
        self._build_menus()

        # Status bar
        self.status_label = QLabel("Starting...")
        sbar = self.statusBar()
        if sbar is not None:
            sbar.addPermanentWidget(self.status_label)

        # System tray (optional; may be unavailable in some environments)
        self.tray = TrayIcon(self) if QSystemTrayIcon.isSystemTrayAvailable() else None

        # Connect signals
        self.event_bus.file_processing_started.connect(self._on_file_started)
        self.event_bus.file_processing_finished.connect(self._on_file_processed)
        self.event_bus.log_message.connect(self.log_widget.append_message)
        self.event_bus.watcher_started.connect(self._on_watcher_started)
        self.event_bus.watcher_stopped.connect(self._on_watcher_stopped)
        self.event_bus.connectivity_changed.connect(self._on_connectivity_changed)

        # Initialize folder status
        cfg = get_config()
        folders = [wf.input_dir for wf in cfg.watched_folders]
        self.dashboard.set_watched_folders(folders)
        self._update_status_bar()

    def _build_menus(self):
        if menu_bar := self.menuBar():
            if file_menu := menu_bar.addMenu("&File"):
                file_menu.addAction("&Settings...", self.open_settings)
                file_menu.addSeparator()
                file_menu.addAction("E&xit", self._quit)

            if help_menu := menu_bar.addMenu("&Help"):
                help_menu.addAction("&About", self._show_about)

    def _on_file_started(self, filepath):
        """Show a 'Processing' row on the dashboard when a file starts."""
        event = ProcessingEvent(
            filepath=filepath,
            filename=os.path.basename(filepath),
            timestamp=datetime.now(),
            success=False,
            pending=True,
        )
        self.dashboard.add_event(event)

    def _on_file_processed(self, event):
        self.dashboard.add_event(event)
        self._update_status_bar()

        # Tray notification
        if self.tray is not None:
            if event.validation_result:
                self.tray.show_validation_notification(event)
            elif not event.success:
                self.tray.show_error_notification(event)

    def _on_watcher_started(self, input_dir):
        self._update_status_bar()

    def _on_watcher_stopped(self, input_dir):
        self._update_status_bar()

    def _on_connectivity_changed(self, is_connected):
        if is_connected:
            self.status_label.setText("Connectivity restored")
        else:
            self.status_label.setText("Connectivity lost - waiting...")

    def _update_status_bar(self):
        cfg = get_config()
        folder_count = len(cfg.watched_folders)
        files_today = self.dashboard.get_event_count()

        # Show queue status if the job queue is active
        queue_info = ""
        try:
            from app.job_queue import get_queue

            queue = get_queue()
            if queue is not None:
                queued = queue.total_queued
                if queued > 0:
                    queue_info = f" | {queued} in queue"
        except Exception:
            pass

        text = (
            f"Watching {folder_count} directories | "
            f"{files_today} files processed today{queue_info}"
        )
        self.status_label.setText(text)
        if self.tray is not None:
            self.tray.update_status(folder_count, files_today)

    def open_settings(self):
        dialog = ConfigDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            QMessageBox.information(
                self,
                "Settings Saved",
                "Settings saved. Restart the application for changes to take effect.",
            )

    def _show_about(self):
        try:
            from app.version import (
                __version__ as version,  # pyright: ignore[reportAttributeAccessIssue]
            )
        except ImportError:
            version = "dev"
        QMessageBox.about(
            self,
            "About PDF Uploader",
            f"PDF Uploader v{version}\n\n"
            "Automated PDF processing and upload to Qualer.\n"
            "Johnson Gage and Inspection, Inc.",
        )

    def _quit(self):
        if inst := QApplication.instance():
            inst.quit()

    def closeEvent(self, a0: Any) -> None:
        """Minimize to tray instead of closing."""
        if self.tray is not None and self.tray.isVisible():
            self.hide()
            a0.ignore()
        else:
            # Fallback: if tray is unavailable/invisible, fully quit.
            self._quit()
            a0.accept()
