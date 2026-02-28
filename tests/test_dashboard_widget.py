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
