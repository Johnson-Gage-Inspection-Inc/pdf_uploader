"""Detail dialog for viewing a single ValidationResult."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

if TYPE_CHECKING:
    from app.event_bus import ProcessingEvent
    from app.po_validator.models import ValidationResult


class DetailDialog(QDialog):
    """Modal dialog showing full validation details for a processed file.

    When a ``validation_result`` is present (PO files), the dialog shows the
    full PO-specific breakdown.  For non-PO files it shows basic upload info.
    """

    _proc_event: ProcessingEvent
    _validation: ValidationResult | None

    def __init__(self, event: ProcessingEvent, parent=None):
        super().__init__(parent)
        self._proc_event = event
        self._validation = event.validation_result  # type: ignore[assignment]

        self.setWindowTitle(f"Details: {event.filename}")
        self.setMinimumSize(700, 500)

        layout = QVBoxLayout(self)

        # Header section — always shown
        header = QGroupBox("Summary")
        h_layout = QFormLayout(header)
        h_layout.addRow("Document:", QLabel(event.filename))

        if self._validation:
            self._build_validation_header(h_layout)
        else:
            self._build_basic_header(h_layout)

        layout.addWidget(header)

        # PO-specific sections
        if self._validation:
            self._build_mismatches_section(layout)
            self._build_missing_items_section(layout)

        # Close button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    # ------------------------------------------------------------------
    # Header helpers
    # ------------------------------------------------------------------

    def _build_basic_header(self, h_layout: QFormLayout):
        """Populate the header for a non-PO (no validation result) file."""
        ev = self._proc_event

        status_text = "Uploaded" if ev.success else "Failed"
        status_color = "green" if ev.success else "red"
        status_label = QLabel(status_text)
        status_label.setStyleSheet(f"font-weight: bold; color: {status_color};")
        h_layout.addRow("Upload:", status_label)

        if ev.work_orders:
            h_layout.addRow("Work Orders:", QLabel(", ".join(ev.work_orders)))
        if ev.service_order_ids:
            h_layout.addRow(
                "Service Orders:",
                QLabel(", ".join(str(s) for s in ev.service_order_ids)),
            )
        if ev.error_message:
            err_label = QLabel(ev.error_message)
            err_label.setStyleSheet("color: red;")
            h_layout.addRow("Error:", err_label)

    def _build_validation_header(self, h_layout: QFormLayout):
        """Populate the header with PO validation detail fields."""
        vr = self._validation
        assert vr is not None  # guarded by caller
        h_layout.addRow("PO Number:", QLabel(vr.po_number or "(unknown)"))
        h_layout.addRow("Service Order:", QLabel(str(vr.service_order_id or "")))

        status_label = QLabel(vr.status.upper())
        status_label.setStyleSheet(f"font-weight: bold; color: {self._status_css()};")
        h_layout.addRow("Status:", status_label)

        h_layout.addRow(
            "Extraction:",
            QLabel(f"{vr.extraction_method} " f"(confidence: {vr.confidence:.0%})"),
        )
        h_layout.addRow(
            "Items Checked:",
            QLabel(f"{vr.line_items_checked} of " f"{vr.work_items_total} work items"),
        )
        h_layout.addRow("Matched:", QLabel(str(vr.line_items_matched)))
        if vr.notes:
            h_layout.addRow("Notes:", QLabel(vr.notes))

    # ------------------------------------------------------------------
    # PO-specific tables
    # ------------------------------------------------------------------

    def _build_mismatches_section(self, layout: QVBoxLayout):
        vr = self._validation
        assert vr is not None
        if not vr.mismatches:
            return
        mm_group = QGroupBox(f"Price Mismatches ({len(vr.mismatches)})")
        mm_layout = QVBoxLayout(mm_group)
        mm_table = QTableWidget()
        mm_table.setColumnCount(5)
        mm_table.setHorizontalHeaderLabels(
            ["S/N", "PO Price", "Expected", "Difference", "Description"]
        )
        mm_table.setRowCount(len(vr.mismatches))
        mm_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        mm_table.setAlternatingRowColors(True)
        for row, m in enumerate(vr.mismatches):
            mm_table.setItem(row, 0, QTableWidgetItem(m.serial_number))
            mm_table.setItem(row, 1, QTableWidgetItem(f"${m.po_price:,.2f}"))
            mm_table.setItem(row, 2, QTableWidgetItem(f"${m.expected_price:,.2f}"))
            diff_item = QTableWidgetItem(f"${m.difference:+,.2f}")
            diff_item.setForeground(QColor("red"))
            mm_table.setItem(row, 3, diff_item)
            mm_table.setItem(row, 4, QTableWidgetItem(getattr(m, "description", "")))
        hdr = mm_table.horizontalHeader()
        assert isinstance(hdr, QHeaderView)
        hdr.setStretchLastSection(True)
        mm_layout.addWidget(mm_table)
        layout.addWidget(mm_group)

    def _build_missing_items_section(self, layout: QVBoxLayout):
        vr = self._validation
        assert vr is not None
        if not vr.missing_items:
            return
        mi_group = QGroupBox(f"Missing Work Items ({len(vr.missing_items)})")
        mi_layout = QVBoxLayout(mi_group)
        mi_table = QTableWidget()
        mi_table.setColumnCount(4)
        mi_table.setHorizontalHeaderLabels(
            ["Work Item ID", "S/N", "Asset", "Expected Price"]
        )
        mi_table.setRowCount(len(vr.missing_items))
        mi_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        mi_table.setAlternatingRowColors(True)
        for row, mi in enumerate(vr.missing_items):
            mi_table.setItem(row, 0, QTableWidgetItem(str(mi.work_item_id)))
            mi_table.setItem(row, 1, QTableWidgetItem(mi.serial_number))
            mi_table.setItem(row, 2, QTableWidgetItem(mi.asset_name))
            price = f"${mi.expected_price:,.2f}" if mi.expected_price else "n/a"
            mi_table.setItem(row, 3, QTableWidgetItem(price))
        hdr = mi_table.horizontalHeader()
        assert isinstance(hdr, QHeaderView)
        hdr.setStretchLastSection(True)
        mi_layout.addWidget(mi_table)
        layout.addWidget(mi_group)

    def _status_css(self):
        vr = self._validation
        assert vr is not None
        return {
            "pass": "green",
            "fail": "red",
            "no_pricing": "orange",
            "extraction_failed": "darkred",
            "skipped": "gray",
        }.get(vr.status, "black")
