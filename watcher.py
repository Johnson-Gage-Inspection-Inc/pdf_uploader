"""
watcher.py is a Python script that watches directories for new PDF files and processes them.
The script uses the watchdog library to monitor directories for new files. When a new PDF file
is detected, the script processes the file and uploads it to Qualer using the upload.py script.

To execute the script, use the command: "python watcher.py" (CLI mode, default from source)
or "python watcher.py --gui" (GUI mode).  The .exe defaults to GUI mode.
"""

import argparse
import time
from threading import Thread

# pip3 install watchdog
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

import app.color_print as cp
import app.pdf as pdf
from app.archive import move_old_pdfs
from app.config import CONFIG, MAX_RUNTIME
from upload import process_file
from app.connectivity import check_connectivity
import sys
import os
from pathlib import Path


def process_pdfs(params):
    for filepath in pdf.next(params[0]):
        process_file(filepath, params)


class PDFFileHandler(FileSystemEventHandler):
    def __init__(self, input_dir, params):
        super().__init__()
        self.input_dir = input_dir
        self.parameters = params
        self.check_interval = 0.1
        self.stability_duration = 1  # seconds

    # Called when a file is created in the input directory
    def on_created(self, event):
        if self.wait_for_file_stability(event.src_path):
            process_pdfs(self.parameters)

    # Called when a file is moved into the input directory or renamed
    def on_moved(self, event):
        if self.wait_for_file_stability(event.dest_path):
            process_pdfs(self.parameters)

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


# Watch a directory for new PDF files
def watch_directory(input_dir, params):
    cp.blue(f'Watching for PDF files in "{input_dir}"...')

    # Emit watcher_started signal for GUI
    try:
        from app.event_bus import get_bus

        bus = get_bus()
        if bus:
            bus.watcher_started.emit(input_dir)
    except Exception:
        pass

    event_handler = PDFFileHandler(input_dir, params)
    observer = Observer()
    observer.schedule(event_handler, input_dir, recursive=False)
    observer.start()

    # Record the start time
    start_time = time.time()

    try:
        while True:
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
                while not check_connectivity():
                    cp.yellow("Retrying connectivity in 30 seconds...")
                    time.sleep(30)  # Retry every 30 seconds
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

            time.sleep(1)
    except KeyboardInterrupt:
        pass  # Exit gracefully
    finally:
        observer.stop()  # Stop the file system watcher
        observer.join()
        # Emit watcher_stopped signal
        try:
            from app.event_bus import get_bus

            bus = get_bus()
            if bus:
                bus.watcher_stopped.emit(input_dir)
        except Exception:
            pass


# Convert a dictionary to a list of lists
def dict_to_list_of_lists(data):
    result = []
    for item in data:
        result.append(list(item.values()))
    return result


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
    try:
        from app.version import __version__
    except ImportError:
        __version__ = "development"
    cp.blue(f"Built from tag: {__version__}")


def launch_cli():
    """Run in CLI mode (original behavior)."""
    check_connectivity()

    threads = []
    for params in dict_to_list_of_lists(CONFIG):
        move_old_pdfs(params[1])  # archive directory
        move_old_pdfs(params[2])  # reject directory
        process_pdfs(params)

        # Create a separate thread to watch each input directory
        input_dir = params[0]
        thread = Thread(target=watch_directory, args=(input_dir, params))
        thread.start()
        threads.append(thread)

    # Wait for all threads to finish
    for thread in threads:
        thread.join()


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
        check_connectivity()
        for params in dict_to_list_of_lists(CONFIG):
            move_old_pdfs(params[1])
            move_old_pdfs(params[2])
            process_pdfs(params)
            input_dir = params[0]
            thread = Thread(
                target=watch_directory, args=(input_dir, params), daemon=True
            )
            thread.start()

    # Start watchers in a background thread to avoid blocking the GUI
    watcher_init_thread = Thread(target=start_watchers, daemon=True)
    watcher_init_thread.start()

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
