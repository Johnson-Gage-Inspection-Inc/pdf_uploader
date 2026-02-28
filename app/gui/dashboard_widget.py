"""Dashboard tab: summary counters + processed files table + folder status."""

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QColor, QDesktopServices
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

QUALER_SO_URL = "https://jgiquality.qualer.com/ServiceOrder/Info"


class SummaryBar(QWidget):
    """Horizontal bar showing today's upload-focused summary counts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.total_label = self._make_label("Total: 0")
        self.uploaded_label = self._make_label("Uploaded: 0", "green")
        self.failed_label = self._make_label("Failed: 0", "red")
        self.no_order_label = self._make_label("No Order: 0", "orange")
        self.processing_label = self._make_label("Processing: 0", "steelblue")

        for lbl in [
            self.total_label,
            self.uploaded_label,
            self.failed_label,
            self.no_order_label,
            self.processing_label,
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
        uploaded = sum(1 for e in events if not e.pending and e.success)
        processing = sum(1 for e in events if e.pending)
        no_order = sum(
            1
            for e in events
            if not e.pending
            and not e.success
            and e.error_message == "No work orders found"
        )
        failed = sum(
            1
            for e in events
            if not e.pending
            and not e.success
            and e.error_message != "No work orders found"
        )

        self.total_label.setText(f"Total: {total}")
        self.uploaded_label.setText(f"Uploaded: {uploaded}")
        self.failed_label.setText(f"Failed: {failed}")
        self.no_order_label.setText(f"No Order: {no_order}")
        self.processing_label.setText(f"Processing: {processing}")


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
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["Time", "Filename", "Upload", "Validation", "WO#", "PO#", "Details"]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        header: QHeaderView = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        self.table.setColumnWidth(0, 70)
        self.table.setColumnWidth(1, 220)
        self.table.setColumnWidth(2, 85)
        self.table.setColumnWidth(3, 85)
        self.table.setColumnWidth(4, 120)
        self.table.setColumnWidth(5, 80)
        layout.addWidget(self.table)

        # Watched folders status
        self.folder_status = QGroupBox("Watched Folders")
        self.folder_layout = QVBoxLayout(self.folder_status)
        layout.addWidget(self.folder_status)

    def add_event(self, event):
        """Add or update a ProcessingEvent on the dashboard.

        If the event is finished (not pending) and a pending event for the
        same filename already exists, the pending row is replaced in place.
        """
        if not event.pending:
            # Replace the matching pending event if one exists
            for i, existing in enumerate(self._events):
                if existing.pending and existing.filename == event.filename:
                    self._events[i] = event
                    self._refresh_table()
                    self.summary_bar.update_counts(self._events)
                    return

        self._events.insert(0, event)
        self._refresh_table()
        self.summary_bar.update_counts(self._events)

    def set_watched_folders(self, folders, statuses=None):
        """Update the watched folders section with clickable links."""
        # Clear existing
        while self.folder_layout.count():
            child = self.folder_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for folder in folders:
            status = (
                "Watching"
                if statuses is None or statuses.get(folder, True)
                else "Stopped"
            )
            color = "green" if status == "Watching" else "red"
            short_name = folder.rstrip("/\\").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
            lbl = QLabel(
                f'<span style="color:{color};">&#9679;</span> '
                f'<a href="{folder}" style="color: #0078D4;">{short_name}</a>'
                f" - {status}"
            )
            lbl.linkActivated.connect(self._open_folder)
            self.folder_layout.addWidget(lbl)

    def _open_folder(self, path):
        """Open a folder in the system file explorer."""
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _refresh_table(self):
        self.table.setRowCount(len(self._events))
        for row, event in enumerate(self._events):
            # Time
            self.table.setItem(
                row, 0, QTableWidgetItem(event.timestamp.strftime("%H:%M:%S"))
            )

            # Filename
            self.table.setItem(row, 1, QTableWidgetItem(event.filename))

            # Upload status
            upload_text = self._upload_status_text(event)
            upload_item = QTableWidgetItem(upload_text)
            upload_item.setForeground(self._upload_status_color(event))
            self.table.setItem(row, 2, upload_item)

            # Validation status
            val_text, val_color = self._validation_status(event)
            val_item = QTableWidgetItem(val_text)
            if val_color:
                val_item.setForeground(val_color)
            self.table.setItem(row, 3, val_item)

            # WO# as clickable hyperlinks (fall back to SO# for PO uploads)
            if event.work_orders or event.service_order_ids:
                wo_label = QLabel()
                links = []
                if event.work_orders:
                    # Show WO numbers linked to their SO URLs
                    for idx, wo in enumerate(event.work_orders):
                        if idx < len(event.service_order_ids):
                            url = f"{QUALER_SO_URL}/{event.service_order_ids[idx]}"
                            links.append(f'<a href="{url}">{wo}</a>')
                        else:
                            links.append(wo)
                else:
                    # PO-based uploads: only SO IDs available
                    for so_id in event.service_order_ids:
                        url = f"{QUALER_SO_URL}/{so_id}"
                        links.append(f'<a href="{url}">SO {so_id}</a>')
                wo_label.setText("  ".join(links))
                wo_label.setOpenExternalLinks(True)
                self.table.setCellWidget(row, 4, wo_label)
            else:
                self.table.setItem(row, 4, QTableWidgetItem(""))

            # PO#
            po_num = ""
            if event.validation_result:
                po_num = event.validation_result.po_number
            self.table.setItem(row, 5, QTableWidgetItem(po_num))

            # View button for validation results
            if event.validation_result:
                btn = QPushButton("View")
                btn.clicked.connect(lambda checked, e=event: self._show_detail(e))
                self.table.setCellWidget(row, 6, btn)

    def _show_detail(self, event):
        from app.gui.detail_dialog import DetailDialog

        dialog = DetailDialog(event, self)
        dialog.exec()

    def _upload_status_text(self, event):
        if event.pending:
            return "Processing"
        if event.success:
            return "Uploaded"
        if event.error_message == "No work orders found":
            return "No Order"
        return "Failed"

    def _upload_status_color(self, event):
        if event.pending:
            return QColor("steelblue")
        if event.success:
            return QColor("green")
        if event.error_message == "No work orders found":
            return QColor("orange")
        return QColor("red")

    def _validation_status(self, event):
        """Return (text, color) for the validation column."""
        if not event.validation_result:
            return ("", None)
        status = event.validation_result.status
        color_map = {
            "pass": QColor("green"),
            "fail": QColor("red"),
            "no_pricing": QColor("orange"),
            "extraction_failed": QColor("darkred"),
            "skipped": QColor("gray"),
        }
        return (status.upper(), color_map.get(status, QColor("black")))

    def get_event_count(self):
        return len(self._events)
