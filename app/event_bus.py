"""
event_bus.py -- Thread-safe signal bridge using Qt signals.

In CLI mode, the bus is never initialized (get_bus() returns None).
In GUI mode, MainWindow connects to these signals to update the UI.

Qt signals are thread-safe: emit() can be called from any thread.
Connected slots execute in the receiver's thread when using
Qt::QueuedConnection (the default for cross-thread connections).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal


@dataclass
class ProcessingEvent:
    """Data object emitted when a file finishes processing."""

    filepath: str
    filename: str
    timestamp: datetime
    success: bool
    work_orders: list[str] = field(default_factory=list)
    service_order_ids: list[int] = field(default_factory=list)
    error_message: str = ""
    validation_result: object = None  # Optional[ValidationResult]
    folder_label: str = ""


class EventBus(QObject):
    """Singleton QObject that emits signals from watcher threads."""

    # File processing lifecycle
    file_processing_started = pyqtSignal(str)  # filepath
    file_processing_finished = pyqtSignal(object)  # ProcessingEvent

    # Watcher lifecycle
    watcher_started = pyqtSignal(str)  # input_dir
    watcher_stopped = pyqtSignal(str)  # input_dir

    # Connectivity
    connectivity_changed = pyqtSignal(bool)  # is_connected

    # Log messages (color_name, text)
    log_message = pyqtSignal(str, str)


# Module-level singleton (None until GUI mode initializes it)
_bus: Optional[EventBus] = None


def get_bus() -> Optional[EventBus]:
    """Get the event bus singleton, or None if not in GUI mode."""
    return _bus


def init_bus() -> EventBus:
    """Initialize the event bus singleton. Call once from launch_gui()."""
    global _bus
    _bus = EventBus()
    return _bus
