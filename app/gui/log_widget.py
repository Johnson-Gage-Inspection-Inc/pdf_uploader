"""Color-coded, read-only, auto-scrolling log viewer widget."""

from datetime import datetime

from PyQt6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import QPlainTextEdit


class LogWidget(QPlainTextEdit):
    """Read-only, auto-scrolling, color-coded log viewer."""

    COLOR_MAP = {
        "red": QColor(220, 50, 50),
        "green": QColor(50, 160, 50),
        "yellow": QColor(180, 140, 20),
        "blue": QColor(50, 100, 220),
        "magenta": QColor(160, 50, 160),
        "cyan": QColor(50, 160, 160),
        "white": QColor(80, 80, 80),
        "black": QColor(0, 0, 0),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumBlockCount(5000)
        self.setFont(QFont("Consolas", 9))
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

    def append_message(self, color_name: str, text: str):
        """Append a timestamped, color-coded message. Thread-safe via Qt signal."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        color = self.COLOR_MAP.get(color_name, QColor(0, 0, 0))

        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        # Timestamp in default color
        default_fmt = QTextCharFormat()
        default_fmt.setForeground(QColor(120, 120, 120))
        cursor.insertText(f"[{timestamp}] ", default_fmt)

        # Message in the specified color
        color_fmt = QTextCharFormat()
        color_fmt.setForeground(color)
        cursor.insertText(text + "\n", color_fmt)

        # Auto-scroll to bottom
        self.setTextCursor(cursor)
        self.ensureCursorVisible()
