"""
watcher.py is a Python script that watches directories for new PDF files and processes them.
The script uses the watchdog library to monitor directories for new files. When a new PDF file
is detected, the script processes the file and uploads it to Qualer using the upload.py script.

To execute the script, use the command: "python3 watcher.py" or "python watcher.py".
"""

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
        if self.wait_for_file_stability(event.src_path):
            process_pdfs(self.parameters)

    def wait_for_file_stability(self, file_path):
        """
        Wait until the file is no longer being written to.
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
                cp.red(f"File not found: {file_path}")
                return False


# Watch a directory for new PDF files
def watch_directory(input_dir, params):
    cp.blue(f'Watching for PDF files in "{input_dir}"...')
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
                while not check_connectivity():
                    cp.yellow("Retrying connectivity in 30 seconds...")
                    time.sleep(30)  # Retry every 30 seconds
                cp.green("Connectivity restored. Resuming monitoring...")

            # Check if the script has been running too long
            if MAX_RUNTIME:
                if time.time() - start_time > MAX_RUNTIME:
                    break  # Exit the loop if the maximum runtime is exceeded

            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()  # Stop the file system watcher if interrupted by the user
        observer.join()


# Convert a dictionary to a list of lists
def dict_to_list_of_lists(data):
    result = []
    for item in data:
        result.append(list(item.values()))
    return result


def main():
    if hasattr(sys, "_MEIPASS"):
        os.chdir(sys._MEIPASS)

    initialize()
    check_connectivity()

    # Process pre-existing PDF files
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


def initialize():
    cp.white("Launching Qualer PDF watcher...")
    exec = sys.executable if getattr(sys, 'frozen', False) else __file__
    exec_path = Path(exec).resolve()
    cp.white(f"Running from: {exec_path}")
    try:
        from app.version import __version__
    except ImportError:
        __version__ = "development"
    cp.white(f"Built from tag: {__version__}")


if __name__ == "__main__":
    main()
