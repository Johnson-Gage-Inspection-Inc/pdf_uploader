"""Single-instance process lock for GUI mode."""

from __future__ import annotations

import os
import tempfile

from PyQt6.QtCore import QLockFile

_lock: QLockFile | None = None


def acquire_single_instance_lock() -> bool:
    """Acquire and hold a process lock. Returns False if another instance holds it."""
    global _lock
    if _lock is not None:
        return True

    lock_path = os.path.join(tempfile.gettempdir(), "pdf_uploader_gui.lock")
    lock = QLockFile(lock_path)
    lock.setStaleLockTime(0)

    if not lock.tryLock(0):
        return False

    _lock = lock
    return True


def release_single_instance_lock() -> None:
    """Release the GUI process lock if held."""
    global _lock
    if _lock is not None:
        _lock.unlock()
        _lock = None
