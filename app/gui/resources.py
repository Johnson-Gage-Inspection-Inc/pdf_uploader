"""Embedded app icon as base64 PNG for PyInstaller-friendly bundling."""

import base64
from PyQt6.QtGui import QIcon, QPixmap

# Simple 32x32 PDF-like icon (red document with "PDF" text)
_ICON_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAAXNSR0IArs4c6QAAAhRJREFUWEft"
    "lj1OwzAYhu+BAxRVYmFgYGNi5gacgIkTcAMOwMTEwMLCgISExMDAjjgBN+AEnICRhZWfT3IS"
    "x/nslCal0kd1nNjv8/7YTkT/+Yn+c/y2A9ba6w7xLCJuIuJBRLyKiAcR8ayq3u0ayYeIeB8R"
    "t6vqYWvMYIBer3cBEacj4kJEHI+IA+n9R0R8joiPEfE8Ih5X1b2+mG2ARqNxDhGnI+JURByJ"
    "iL0qfhcR7yPibUTcq6rHXTDbAI1G42xEnImIkxFxJCL2pu+/IuJbRHyOiGcRcaeqnnQBbQM0"
    "m82TiDgVEcci4nBE7EnfA/AtIr5GxMuIuFNVT7uAtgGazebRiDgREUcj4lBE7E7ff0bE94j4"
    "EhEvIuJuVT3rAtoGaDabDRGnI+J4RByMiP3p+8+I+BERXyPiZUTcr6rnXUDbAL1e70hEnIyI"
    "YxFxICL2pe8/IuJ7RHyOiKcRcaeqXnQBbQP0er2DEXEqIo5HxIGI2Ju+/4yIHxHxLSKeR8S9"
    "qnrZBbQNkE7B0xFxIiIORsT+9P1XRHyPiC8R8TQi7lbVqy6gbQCAZrN5PCJOR8SxiDgQEfvS"
    "958R8SMivkXEs4i4W1Wvu4C2AQCazWYjIk5FxImIOBQR+9P3XxHJKeJ7RHyJiGcRca+q3nQB"
    "bQMANJvNgxFxOiJORMShiNiXvv+KiB8R8TUinkfE/ap62wXU/gP8BqJCbyC3qLLFAAAAAElF"
    "TkSuQmCC"
)


def get_app_icon() -> QIcon:
    """Return the application icon as a QIcon."""
    pixmap = QPixmap()
    pixmap.loadFromData(base64.b64decode(_ICON_BASE64))
    return QIcon(pixmap)
