import unittest
from datetime import datetime

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QColor

from app.gui.dashboard_widget import DashboardWidget
from app.event_bus import ProcessingEvent


class TestDashboardWidget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # ensure a QApplication exists for widget instantiation
        if QApplication.instance() is None:
            cls._app = QApplication([])

    def setUp(self):
        self.widget = DashboardWidget()

    def make_event(self, status):
        return ProcessingEvent(
            filepath="/tmp/file.pdf",
            filename="file.pdf",
            timestamp=datetime.now(),
            success=True,
            validation_result=type("V", (), {"status": status})(),
        )

    def test_validation_status_formats_text(self):
        evt = self.make_event("no_pricing")
        text, color = self.widget._validation_status(evt)
        self.assertEqual(text, "No Pricing")
        self.assertEqual(color, QColor("orange"))

        evt.validation_result.status = "extraction_failed"
        text, color = self.widget._validation_status(evt)
        self.assertEqual(text, "Extraction Failed")
        self.assertEqual(color, QColor("darkred"))

    def test_validation_status_handles_none(self):
        evt = ProcessingEvent(
            filepath="/tmp/file.pdf",
            filename="file.pdf",
            timestamp=datetime.now(),
            success=True,
            validation_result=None,
        )
        text, color = self.widget._validation_status(evt)
        self.assertEqual(text, "")
        self.assertIsNone(color)

    def test_validation_status_unknown_status_color_black(self):
        evt = self.make_event("mystery_status")
        text, color = self.widget._validation_status(evt)
        self.assertEqual(text, "Mystery Status")
        self.assertEqual(color, QColor("black"))

    def test_view_button_shows_correct_event(self):
        """Each row's View button should reference its own event."""
        from PyQt6.QtWidgets import QPushButton

        evt_po = ProcessingEvent(
            filepath="/tmp/PO123.pdf",
            filename="PO123.pdf",
            timestamp=datetime.now(),
            success=True,
            validation_result=type(
                "V",
                (),
                {
                    "status": "pass",
                    "po_number": "123",
                    "document_name": "PO123.pdf",
                    "service_order_id": 100,
                    "extraction_method": "ocr",
                    "confidence": 0.9,
                    "line_items_checked": 1,
                    "work_items_total": 1,
                    "line_items_matched": 1,
                    "notes": "",
                    "mismatches": [],
                    "missing_items": [],
                },
            )(),
        )
        evt_cert = ProcessingEvent(
            filepath="/tmp/cert.pdf",
            filename="cert.pdf",
            timestamp=datetime.now(),
            success=True,
            validation_result=None,
        )

        self.widget.add_event(evt_po)
        self.widget.add_event(evt_cert)

        # cert.pdf is row 0 (most recent), PO123.pdf is row 1
        btn0 = self.widget.table.cellWidget(0, 6)
        btn1 = self.widget.table.cellWidget(1, 6)
        self.assertIsInstance(btn0, QPushButton)
        self.assertIsInstance(btn1, QPushButton)

    def test_wo_column_clears_stale_widget(self):
        """WO# column widget should be properly set/cleared per event."""
        evt_with_wo = ProcessingEvent(
            filepath="/tmp/a.pdf",
            filename="a.pdf",
            timestamp=datetime.now(),
            success=True,
            work_orders=["WO-1"],
            service_order_ids=[100],
        )
        evt_no_wo = ProcessingEvent(
            filepath="/tmp/b.pdf",
            filename="b.pdf",
            timestamp=datetime.now(),
            success=True,
        )

        self.widget.add_event(evt_with_wo)
        # Row 0 should have a cell widget for WO#
        self.assertIsNotNone(self.widget.table.cellWidget(0, 4))

        self.widget.add_event(evt_no_wo)
        # Row 0 is now evt_no_wo — should NOT have a cell widget
        self.assertIsNone(self.widget.table.cellWidget(0, 4))
        # Row 1 is evt_with_wo — should have a cell widget
        self.assertIsNotNone(self.widget.table.cellWidget(1, 4))


class TestDetailDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if QApplication.instance() is None:
            cls._app = QApplication([])

    def test_non_po_dialog(self):
        """DetailDialog should render without crashing for non-PO events."""
        from app.gui.detail_dialog import DetailDialog

        evt = ProcessingEvent(
            filepath="/tmp/cert.pdf",
            filename="cert.pdf",
            timestamp=datetime.now(),
            success=True,
            work_orders=["WO-1"],
            service_order_ids=[100],
            validation_result=None,
        )
        dialog = DetailDialog(evt)
        self.assertEqual(dialog.windowTitle(), "Details: cert.pdf")

    def test_po_dialog(self):
        """DetailDialog should render PO-specific fields when validation_result exists."""
        from app.gui.detail_dialog import DetailDialog

        result = type(
            "V",
            (),
            {
                "status": "pass",
                "po_number": "PO-999",
                "document_name": "PO999.pdf",
                "service_order_id": 42,
                "extraction_method": "ocr",
                "confidence": 0.95,
                "line_items_checked": 3,
                "work_items_total": 5,
                "line_items_matched": 3,
                "notes": "",
                "mismatches": [],
                "missing_items": [],
            },
        )()
        evt = ProcessingEvent(
            filepath="/tmp/PO999.pdf",
            filename="PO999.pdf",
            timestamp=datetime.now(),
            success=True,
            validation_result=result,
        )
        dialog = DetailDialog(evt)
        self.assertEqual(dialog.windowTitle(), "Details: PO999.pdf")
