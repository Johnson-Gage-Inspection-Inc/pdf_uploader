"""
watcher.py is a Python script that watches directories for new PDF files and processes them.
The script uses the watchdog library to monitor directories for new files. When a new PDF file
is detected, the script processes the file and uploads it to Qualer using the upload.py script.

To execute the script, use the command: "python watcher.py" (CLI mode, default from source)
or "python watcher.py --gui" (GUI mode).  The .exe defaults to GUI mode.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Any

# pip3 install watchdog
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

import app.color_print as cp
import app.pdf as pdf
from app.archive import move_old_pdfs
from app.config import MAX_RUNTIME
from app.config_manager import get_config, WatchedFolder
from upload import process_file
from app.connectivity import check_connectivity

# Module-level shutdown event — set to request all watchers to stop.
_shutdown_event = Event()

# Track active observers so they can be stopped on exit.
_active_observers: list[Any] = []
_observers_lock = Lock()


def process_pdfs(folder: WatchedFolder):
    for filepath in pdf.next(folder.input_dir):
        process_file(filepath, folder)


class PDFFileHandler(FileSystemEventHandler):
    def __init__(self, input_dir: str, folder: WatchedFolder):
        super().__init__()
        self.input_dir = input_dir
        self.folder = folder
        self.check_interval = 0.1
        self.stability_duration = 1  # seconds

    # Called when a file is created in the input directory
    def on_created(self, event):
        if self.wait_for_file_stability(event.src_path):
            try:
                process_pdfs(self.folder)
            except Exception:
                import traceback

                traceback.print_exc()

    # Called when a file is moved into the input directory or renamed
    def on_moved(self, event):
        if self.wait_for_file_stability(event.dest_path):
            try:
                process_pdfs(self.folder)
            except Exception:
                import traceback

                traceback.print_exc()

    def wait_for_file_stability(self, file_path):
        """
        Wait until the file is no longer being written to,
        by checking if the file size remains the same for a certain duration.
        """
        previous_size = -1
        stable_time = 0

        while True:
            try:
                current_size = os.path.getsize(file_path)
                if current_size == previous_size:
                    stable_time += self.check_interval
                else:
                    stable_time = 0

                if stable_time >= self.stability_duration:
                    cp.white(f"File is stable: {file_path}")
                    return True

                previous_size = current_size
                time.sleep(self.check_interval)
            except FileNotFoundError:
                cp.yellow(f"File not found: {file_path}")
                return False


def request_shutdown():
    """Signal all watcher loops to stop and clean up observers."""
    _shutdown_event.set()
    with _observers_lock:
        snapshot = list(_active_observers)
    for obs in snapshot:
        try:
            obs.stop()
        except Exception as exc:
            cp.yellow(f"Warning: failed to stop observer {obs!r}: {exc}")


# Watch a directory for new PDF files
def watch_directory(folder: WatchedFolder):
    cp.blue(f'Watching for PDF files in "{folder.input_dir}"...')

    # Emit watcher_started signal for GUI
    try:
        from app.event_bus import get_bus

        bus = get_bus()
        if bus:
            bus.watcher_started.emit(folder.input_dir)
    except Exception:
        pass

    event_handler = PDFFileHandler(folder.input_dir, folder)
    observer = Observer()
    observer.daemon = True  # Ensure observer thread won't block exit
    observer.schedule(event_handler, folder.input_dir, recursive=False)
    observer.start()
    with _observers_lock:
        _active_observers.append(observer)

    # Record the start time
    start_time = time.time()

    try:
        while not _shutdown_event.is_set():
            # Periodically check connectivity
            if not check_connectivity():
                cp.red("Connectivity lost. Pausing monitoring...")
                # Emit connectivity lost
                try:
                    from app.event_bus import get_bus

                    bus = get_bus()
                    if bus:
                        bus.connectivity_changed.emit(False)
                except Exception:
                    pass
                while not check_connectivity() and not _shutdown_event.is_set():
                    cp.yellow("Retrying connectivity in 30 seconds...")
                    _shutdown_event.wait(30)  # Interruptible sleep
                if _shutdown_event.is_set():
                    break
                cp.green("Connectivity restored. Resuming monitoring...")
                try:
                    from app.event_bus import get_bus

                    bus = get_bus()
                    if bus:
                        bus.connectivity_changed.emit(True)
                except Exception:
                    pass

            # Check if the script has been running too long
            if MAX_RUNTIME:
                if time.time() - start_time > MAX_RUNTIME:
                    break  # Exit the loop if the maximum runtime is exceeded

            _shutdown_event.wait(1)  # Interruptible sleep
    except KeyboardInterrupt:
        pass  # Exit gracefully
    finally:
        observer.stop()  # Stop the file system watcher
        observer.join(timeout=3)
        # Only treat the watcher as stopped if the observer thread has actually terminated
        if observer.is_alive():
            # Keep it in _active_observers so it can still be shut down later
            cp.yellow(
                f'Watcher thread for "{folder.input_dir}" did not stop within timeout; '
                "keeping observer active."
            )
        else:
            with _observers_lock:
                if observer in _active_observers:
                    _active_observers.remove(observer)
            # Emit watcher_stopped signal
            try:
                from app.event_bus import get_bus

                bus = get_bus()
                if bus:
                    bus.watcher_stopped.emit(folder.input_dir)
            except Exception:
                pass


def parse_args():
    parser = argparse.ArgumentParser(description="PDF Uploader / Watcher")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--gui", action="store_true", help="Launch with GUI (default for .exe)"
    )
    group.add_argument("--cli", action="store_true", help="Run in CLI/console mode")
    return parser.parse_args()


def initialize():
    cp.white("Launching Qualer PDF watcher...")
    executable = sys.executable if getattr(sys, "frozen", False) else __file__
    exec_path = Path(executable).resolve()
    cp.blue(f"Running from: {exec_path}")
    version = "development"
    try:
        from app.version import (
            __version__,  # pyright: ignore[reportAttributeAccessIssue]
        )

        version = __version__
    except (ImportError, AttributeError):
        pass
    cp.blue(f"Built from tag: {version}")


def launch_cli():
    """Run in CLI mode (original behavior)."""
    from app.auth import ensure_authenticated

    ensure_authenticated()
    check_connectivity()

    threads = []
    for folder in get_config().watched_folders:
        move_old_pdfs(folder.output_dir)
        move_old_pdfs(folder.reject_dir)
        process_pdfs(folder)

        # Create a separate thread to watch each input directory
        thread = Thread(target=watch_directory, args=(folder,))
        thread.start()
        threads.append(thread)

    # Wait for all threads to finish (interruptible)
    try:
        for thread in threads:
            while thread.is_alive():
                thread.join(timeout=1)
    except KeyboardInterrupt:
        cp.yellow("Shutting down...")
        request_shutdown()
        for thread in threads:
            thread.join(timeout=5)


def launch_gui():
    """Start Qt application with GUI."""
    from PyQt6.QtWidgets import QApplication
    from app.event_bus import init_bus
    from app.gui.main_window import MainWindow
    from app.color_print import set_gui_handler, set_console_enabled

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Keep running in tray

    # Initialize event bus
    bus = init_bus()

    # Wire color_print to event bus
    set_gui_handler(lambda color, text: bus.log_message.emit(color, text))
    if getattr(sys, "frozen", False):
        set_console_enabled(False)

    # Create main window
    window = MainWindow(bus)
    window.show()

    # Start watcher threads (daemon=True so they die when Qt event loop exits)
    def start_watchers():
        from app.auth import ensure_authenticated, AuthenticationError

        try:
            ensure_authenticated()
            check_connectivity()
        except AuthenticationError as exc:
            # Surface authentication failures via the GUI event bus and abort startup
            bus.log_message.emit("red", f"Authentication failed: {exc}")
            request_shutdown()
            return
        for folder in get_config().watched_folders:
            move_old_pdfs(folder.output_dir)
            move_old_pdfs(folder.reject_dir)
            process_pdfs(folder)
            thread = Thread(target=watch_directory, args=(folder,), daemon=True)
            thread.start()

    # Start watchers in a background thread to avoid blocking the GUI
    watcher_init_thread = Thread(target=start_watchers, daemon=True)
    watcher_init_thread.start()

    # Ensure watchers are stopped and process exits when the app quits
    def _on_about_to_quit():
        request_shutdown()

    app.aboutToQuit.connect(_on_about_to_quit)

    sys.exit(app.exec())


def main():
    args = parse_args()

    if hasattr(sys, "_MEIPASS"):
        os.chdir(getattr(sys, "_MEIPASS"))

    initialize()

    # Default: .exe -> GUI, source -> CLI
    use_gui = args.gui or (getattr(sys, "frozen", False) and not args.cli)

    if use_gui:
        launch_gui()
    else:
        launch_cli()


if __name__ == "__main__":
    # Required for PyInstaller on Windows to prevent infinite process spawning
    import multiprocessing

    multiprocessing.freeze_support()
    main()
