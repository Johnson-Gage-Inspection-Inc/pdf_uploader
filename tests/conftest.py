"""
conftest.py - Test configuration and isolation.

Handles the sys.modules contamination from test_upload.py, which mocks app
modules at module level (necessary because upload.py has module-level code).
"""

import sys
import os
import tempfile
from unittest.mock import MagicMock

import pytest


def pytest_configure(config):
    """Run before test collection. Set up environment for real module imports."""
    os.environ.setdefault("QUALER_API_KEY", "00000000-0000-0000-0000-000000000000")

    # Import and patch config before color_print tries to use LOG_FILE
    import app.config

    app.config.LOG_FILE = os.path.join(tempfile.gettempdir(), "test_pdfUploader.log")

    # Force import real app modules now, with patched config.
    # Some modules may fail to import if optional dependencies (fitz, tesseract)
    # are not installed - that's OK, we just skip them.
    # Mock fitz if not available (needed by app.orientation)
    if "fitz" not in sys.modules:
        mock_fitz = MagicMock()
        sys.modules["fitz"] = mock_fitz

    for mod in [
        "app.color_print",
        "app.pdf",
        "app.connectivity",
        "app.archive",
        "app.api",
        "app.PurchaseOrders",
        "app.orientation",
        "app.qualer_client",
    ]:
        try:
            __import__(mod)
        except (ImportError, Exception):
            pass

    # Save references to real modules before test_upload.py replaces them
    config._real_app_modules = {
        k: v for k, v in sys.modules.items() if k.startswith("app")
    }


@pytest.fixture(autouse=True)
def _restore_real_app_modules(request):
    """Restore real app modules before each test, unless it's a test_upload test."""
    if "test_upload" in request.node.nodeid:
        yield
        return

    real = request.config._real_app_modules
    # Restore real modules that were replaced by mocks
    for k, v in real.items():
        if k in sys.modules and isinstance(sys.modules[k], MagicMock):
            sys.modules[k] = v
        elif k not in sys.modules:
            sys.modules[k] = v
    yield
