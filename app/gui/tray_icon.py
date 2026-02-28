"""System tray icon with context menu and balloon notifications."""

from PyQt6.QtWidgets import QMenu, QSystemTrayIcon


class TrayIcon(QSystemTrayIcon):
    """System tray icon with context menu and notification support."""

    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window

        from app.gui.resources import get_app_icon

        self.setIcon(get_app_icon())
        self.setToolTip("PDF Uploader - Starting...")

        # Context menu
        menu = QMenu()
        menu.addAction("Show Window", self._show_window)
        menu.addSeparator()
        self.status_action = menu.addAction("Status: Starting...")
        self.status_action.setEnabled(False)
        menu.addSeparator()
        menu.addAction("Settings...", main_window.open_settings)
        menu.addSeparator()
        menu.addAction("Quit", self._quit)
        self.setContextMenu(menu)

        # Double-click to show window
        self.activated.connect(self._on_activated)
        self.show()

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_window()

    def _show_window(self):
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()

    def _quit(self):
        from PyQt6.QtWidgets import QApplication

        QApplication.instance().quit()

    def show_validation_notification(self, event):
        """Show balloon notification for a validation result."""
        result = event.validation_result
        if result.status == "pass":
            title = "PO Validated"
            msg = f"{event.filename}: All prices match"
            icon = QSystemTrayIcon.MessageIcon.Information
        elif result.status == "fail":
            n_mismatches = len(result.mismatches)
            n_missing = len(result.missing_items)
            title = "PO Validation Failed"
            msg = f"{event.filename}: {n_mismatches} mismatch(es), {n_missing} missing"
            icon = QSystemTrayIcon.MessageIcon.Warning
        else:
            title = "PO Validation"
            msg = f"{event.filename}: {result.status}"
            icon = QSystemTrayIcon.MessageIcon.Information

        self.showMessage(title, msg, icon, 5000)

    def show_error_notification(self, event):
        """Show balloon notification for an upload error."""
        self.showMessage(
            "Upload Failed",
            f"{event.filename}: {event.error_message or 'See log for details'}",
            QSystemTrayIcon.MessageIcon.Critical,
            5000,
        )

    def update_status(self, folder_count, files_today):
        """Update the tray tooltip and status menu item."""
        text = f"Watching {folder_count} folders | {files_today} processed today"
        self.status_action.setText(f"Status: {text}")
        self.setToolTip(f"PDF Uploader - {text}")
