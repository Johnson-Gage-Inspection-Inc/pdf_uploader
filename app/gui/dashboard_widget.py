"""Dashboard tab: summary counters + processed files table + folder status."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class SummaryBar(QWidget):
    """Horizontal bar showing today's summary counts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.total_label = self._make_label("Total: 0")
        self.pass_label = self._make_label("Pass: 0", "green")
        self.fail_label = self._make_label("Fail: 0", "red")
        self.error_label = self._make_label("Errors: 0", "darkred")
        self.skip_label = self._make_label("Skipped: 0", "gray")

        for lbl in [
            self.total_label,
            self.pass_label,
            self.fail_label,
            self.error_label,
            self.skip_label,
        ]:
            layout.addWidget(lbl)

    def _make_label(self, text, color=None):
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        style = "font-size: 13px; font-weight: bold; padding: 6px 12px;"
        if color:
            style += f" color: {color};"
        lbl.setStyleSheet(style)
        return lbl

    def update_counts(self, events):
        total = len(events)
        passed = sum(
            1
            for e in events
            if e.validation_result and e.validation_result.status == "pass"
        )
        failed = sum(
            1
            for e in events
            if e.validation_result and e.validation_result.status == "fail"
        )
        errors = sum(1 for e in events if not e.success)
        skipped = sum(
            1
            for e in events
            if e.validation_result
            and e.validation_result.status in ("skipped", "no_pricing")
        )

        self.total_label.setText(f"Total: {total}")
        self.pass_label.setText(f"Pass: {passed}")
        self.fail_label.setText(f"Fail: {failed}")
        self.error_label.setText(f"Errors: {errors}")
        self.skip_label.setText(f"Skipped: {skipped}")


class DashboardWidget(QWidget):
    """Main dashboard tab with summary, file table, and folder status."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._events = []

        layout = QVBoxLayout(self)

        # Summary bar
        self.summary_bar = SummaryBar()
        layout.addWidget(self.summary_bar)

        # Processed files table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["Time", "Filename", "Status", "SO#", "PO#", "Details"]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        self.table.setColumnWidth(0, 70)
        self.table.setColumnWidth(1, 220)
        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(3, 80)
        self.table.setColumnWidth(4, 80)
        layout.addWidget(self.table)

        # Watched folders status
        self.folder_status = QGroupBox("Watched Folders")
        self.folder_layout = QVBoxLayout(self.folder_status)
        layout.addWidget(self.folder_status)

    def add_event(self, event):
        """Add a ProcessingEvent to the dashboard."""
        self._events.insert(0, event)
        self._refresh_table()
        self.summary_bar.update_counts(self._events)

    def set_watched_folders(self, folders, statuses=None):
        """Update the watched folders section."""
        # Clear existing
        while self.folder_layout.count():
            child = self.folder_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for i, folder in enumerate(folders):
            status = (
                "Watching"
                if statuses is None or statuses.get(folder, True)
                else "Stopped"
            )
            color = "green" if status == "Watching" else "red"
            # Use just the folder name, not the full path
            short_name = folder.rstrip("/\\").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
            lbl = QLabel(
                f'<span style="color:{color};">&#9679;</span> {short_name} - {status}'
            )
            self.folder_layout.addWidget(lbl)

    def _refresh_table(self):
        self.table.setRowCount(len(self._events))
        for row, event in enumerate(self._events):
            # Time
            self.table.setItem(
                row, 0, QTableWidgetItem(event.timestamp.strftime("%H:%M:%S"))
            )

            # Filename
            self.table.setItem(row, 1, QTableWidgetItem(event.filename))

            # Status
            status_text = self._status_text(event)
            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(self._status_color(event))
            self.table.setItem(row, 2, status_item)

            # SO#
            so_ids = ", ".join(str(s) for s in event.service_order_ids)
            self.table.setItem(row, 3, QTableWidgetItem(so_ids))

            # PO#
            po_num = ""
            if event.validation_result:
                po_num = event.validation_result.po_number
            self.table.setItem(row, 4, QTableWidgetItem(po_num))

            # View button for validation results
            if event.validation_result:
                btn = QPushButton("View")
                btn.clicked.connect(lambda checked, e=event: self._show_detail(e))
                self.table.setCellWidget(row, 5, btn)

    def _show_detail(self, event):
        from app.gui.detail_dialog import DetailDialog

        dialog = DetailDialog(event, self)
        dialog.exec()

    def _status_text(self, event):
        if event.validation_result:
            return event.validation_result.status.upper()
        return "OK" if event.success else "ERROR"

    def _status_color(self, event):
        if event.validation_result:
            return {
                "pass": QColor("green"),
                "fail": QColor("red"),
                "no_pricing": QColor("orange"),
                "extraction_failed": QColor("darkred"),
                "skipped": QColor("gray"),
            }.get(event.validation_result.status, QColor("black"))
        return QColor("green") if event.success else QColor("red")

    def get_event_count(self):
        return len(self._events)
