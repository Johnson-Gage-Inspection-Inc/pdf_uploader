"""Main application window with tabs, menu bar, status bar, and system tray."""

from PyQt6.QtWidgets import (
    QDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QTabWidget,
)

from app.config_manager import get_config
from app.event_bus import EventBus
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
        self.statusBar().addPermanentWidget(self.status_label)

        # System tray
        self.tray = TrayIcon(self)

        # Connect signals
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
        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction("&Settings...", self.open_settings)
        file_menu.addSeparator()
        file_menu.addAction("E&xit", self._quit)

        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addAction("&About", self._show_about)

    def _on_file_processed(self, event):
        self.dashboard.add_event(event)
        self._update_status_bar()

        # Tray notification
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
        text = (
            f"Watching {folder_count} directories | {files_today} files processed today"
        )
        self.status_label.setText(text)
        self.tray.update_status(folder_count, files_today)

    def open_settings(self):
        from app.gui.config_dialog import ConfigDialog

        dialog = ConfigDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            QMessageBox.information(
                self,
                "Settings Saved",
                "Settings saved. Restart the application for changes to take effect.",
            )

    def _show_about(self):
        try:
            from app.version import version
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
        from PyQt6.QtWidgets import QApplication

        QApplication.instance().quit()

    def closeEvent(self, event):
        """Minimize to tray instead of closing."""
        if self.tray.isVisible():
            self.hide()
            event.ignore()
        else:
            event.accept()
