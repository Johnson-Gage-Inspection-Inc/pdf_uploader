"""App icon loader — prefers bundled file, falls back to embedded base64."""

import base64
import os
import sys

from PyQt6.QtGui import QIcon, QPixmap


def _resolve_icon_path() -> str | None:
    """Return the absolute path to the bundled icon file, or None."""
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
    for name in ("img/app.ico", "img/app_icon_32.png"):
        path = os.path.join(base, name)
        if os.path.isfile(path):
            return path
    return None


# Fallback 32x32 icon encoded as base64 PNG (generated from img/app_icon_32.png)
_ICON_BASE64 = ""


def _load_base64() -> str:
    """Lazily load the base64 string from the generated text file."""
    b64_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "img",
        "_icon_b64.txt",
    )
    if os.path.isfile(b64_path):
        with open(b64_path, "r") as f:
            return f.read().strip()
    return _ICON_BASE64


def get_app_icon() -> QIcon:
    """Return the application icon as a QIcon."""
    # Try loading from bundled file first (most reliable)
    path = _resolve_icon_path()
    if path:
        icon = QIcon(path)
        if not icon.isNull():
            return icon

    # Fallback to embedded base64
    b64 = _load_base64()
    if b64:
        pixmap = QPixmap()
        pixmap.loadFromData(base64.b64decode(b64))
        if not pixmap.isNull():
            return QIcon(pixmap)

    return QIcon()
