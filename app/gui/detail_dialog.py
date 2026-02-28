"""Detail dialog for viewing a single ValidationResult."""

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


class DetailDialog(QDialog):
    """Modal dialog showing full validation details for a single PO."""

    def __init__(self, event, parent=None):
        super().__init__(parent)
        self.event = event
        self.result = event.validation_result

        self.setWindowTitle(f"Validation Details: {event.filename}")
        self.setMinimumSize(700, 500)

        layout = QVBoxLayout(self)

        # Header section
        header = QGroupBox("Summary")
        h_layout = QFormLayout(header)
        h_layout.addRow("Document:", QLabel(self.result.document_name))
        h_layout.addRow("PO Number:", QLabel(self.result.po_number or "(unknown)"))
        h_layout.addRow(
            "Service Order:", QLabel(str(self.result.service_order_id or ""))
        )

        status_label = QLabel(self.result.status.upper())
        status_label.setStyleSheet(f"font-weight: bold; color: {self._status_css()};")
        h_layout.addRow("Status:", status_label)

        h_layout.addRow(
            "Extraction:",
            QLabel(
                f"{self.result.extraction_method} "
                f"(confidence: {self.result.confidence:.0%})"
            ),
        )
        h_layout.addRow(
            "Items Checked:",
            QLabel(
                f"{self.result.line_items_checked} of "
                f"{self.result.work_items_total} work items"
            ),
        )
        h_layout.addRow("Matched:", QLabel(str(self.result.line_items_matched)))
        if self.result.notes:
            h_layout.addRow("Notes:", QLabel(self.result.notes))
        layout.addWidget(header)

        # Mismatches table
        if self.result.mismatches:
            mm_group = QGroupBox(f"Price Mismatches ({len(self.result.mismatches)})")
            mm_layout = QVBoxLayout(mm_group)
            mm_table = QTableWidget()
            mm_table.setColumnCount(5)
            mm_table.setHorizontalHeaderLabels(
                ["S/N", "PO Price", "Expected", "Difference", "Description"]
            )
            mm_table.setRowCount(len(self.result.mismatches))
            mm_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            mm_table.setAlternatingRowColors(True)
            for row, m in enumerate(self.result.mismatches):
                mm_table.setItem(row, 0, QTableWidgetItem(m.serial_number))
                mm_table.setItem(row, 1, QTableWidgetItem(f"${m.po_price:,.2f}"))
                mm_table.setItem(row, 2, QTableWidgetItem(f"${m.expected_price:,.2f}"))
                diff_item = QTableWidgetItem(f"${m.difference:+,.2f}")
                diff_item.setForeground(QColor("red"))
                mm_table.setItem(row, 3, diff_item)
                mm_table.setItem(
                    row, 4, QTableWidgetItem(getattr(m, "description", ""))
                )
            mm_table.horizontalHeader().setStretchLastSection(True)
            mm_layout.addWidget(mm_table)
            layout.addWidget(mm_group)

        # Missing items table
        if self.result.missing_items:
            mi_group = QGroupBox(
                f"Missing Work Items ({len(self.result.missing_items)})"
            )
            mi_layout = QVBoxLayout(mi_group)
            mi_table = QTableWidget()
            mi_table.setColumnCount(4)
            mi_table.setHorizontalHeaderLabels(
                ["Work Item ID", "S/N", "Asset", "Expected Price"]
            )
            mi_table.setRowCount(len(self.result.missing_items))
            mi_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            mi_table.setAlternatingRowColors(True)
            for row, mi in enumerate(self.result.missing_items):
                mi_table.setItem(row, 0, QTableWidgetItem(str(mi.work_item_id)))
                mi_table.setItem(row, 1, QTableWidgetItem(mi.serial_number))
                mi_table.setItem(row, 2, QTableWidgetItem(mi.asset_name))
                price = f"${mi.expected_price:,.2f}" if mi.expected_price else "n/a"
                mi_table.setItem(row, 3, QTableWidgetItem(price))
            mi_table.horizontalHeader().setStretchLastSection(True)
            mi_layout.addWidget(mi_table)
            layout.addWidget(mi_group)

        # Close button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _status_css(self):
        return {
            "pass": "green",
            "fail": "red",
            "no_pricing": "orange",
            "extraction_failed": "darkred",
            "skipped": "gray",
        }.get(self.result.status, "black")
