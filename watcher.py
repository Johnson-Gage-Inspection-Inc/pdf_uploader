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
from app.config import CONFIG, DELETE_MODE, MAX_RUNTIME
from upload import process_file
from app.connectivity import check_connectivity


def process_pdfs(parameters):
    cp.white(f'Checking for PDF files in "{parameters[0]}"...')
    for filepath in pdf.next(parameters[0]):
        process_file(filepath, parameters)


class PDFFileHandler(FileSystemEventHandler):
    def __init__(self, input_dir, parameters):
        super().__init__()
        self.input_dir = input_dir
        self.parameters = parameters

    # Called when a file is created in the input directory
    def on_created(self, event):
        time.sleep(3)  # Wait for the file to finish writing
        process_pdfs(self.parameters)

    # Called when a file is moved into the input directory or renamed
    def on_moved(self, event):
        time.sleep(1)  # Wait for the file to finish writing
        process_pdfs(self.parameters)


# Watch a directory for new PDF files
def watch_directory(input_dir, parameters):
    cp.blue("Watching for PDF files in \"" + input_dir + "\"...")
    event_handler = PDFFileHandler(input_dir, parameters)
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


cp.white("Launching Qualer PDF watcher...")
check_connectivity()

qualer_parameter_sets = dict_to_list_of_lists(CONFIG)

# Process pre-existing PDF files
for qualer_parameters in qualer_parameter_sets:
    move_old_pdfs(qualer_parameters[1], DELETE_MODE)  # Check for and move PDFs in the archive directory not created today
    move_old_pdfs(qualer_parameters[2], DELETE_MODE)  # Check for and move PDFs in the reject directory not created today
    process_pdfs(qualer_parameters)

# Create a separate thread to watch each input directory
threads = []
for parameters in qualer_parameter_sets:
    input_dir = parameters[0]
    thread = Thread(target=watch_directory, args=(input_dir, parameters))
    thread.start()
    threads.append(thread)

# Wait for all threads to finish
for thread in threads:
    thread.join()
