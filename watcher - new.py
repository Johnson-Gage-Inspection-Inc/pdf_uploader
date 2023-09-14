"""

watcher.py is a Python script that watches directories for new PDF files and processes them.

To execute the script, use the command: "python3 watcher.py" or "python watcher.py".

Dependencies:
    - watchdog: pip3 install watchdog

"""
from time import sleep, time
from threading import Thread

# pip3 install watchdog
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

import app.color_print as cp
import app.pdf as pdf
from app.archive import move_old_pdfs
from config import CONFIG, DELETE_MODE
from upload import process_file

def process_pdfs(parameters):
    print("Checking for PDF files in \"", parameters[0], "\"...")
    for filepath in pdf.next(parameters[0]):
        process_file(filepath, parameters)

class PDFFileHandler(FileSystemEventHandler):
    def __init__(self, input_dir, parameters):
        super().__init__()
        self.input_dir = input_dir
        self.parameters = parameters
        self.file_modification_times = {}

    def on_created(self, event):
        self.start_processing(event.src_path)

    def on_modified(self, event):
        self.update_modification_time(event.src_path)

    def start_processing(self, filepath):
        self.update_modification_time(filepath)
        Thread(target=self.process_if_finished, args=(filepath,)).start()

    def update_modification_time(self, filepath):
        self.file_modification_times[filepath] = time()

    def process_if_finished(self, filepath):
        while True:
            current_time = time()
            last_modification_time = self.file_modification_times.get(filepath, 0)
            time_elapsed = current_time - last_modification_time
            
            # Wait for a certain period (e.g., 2 seconds) to consider the file finished
            if time_elapsed >= 2:
                process_pdfs(self.parameters)
                break
            else:
                sleep(1)


# Watch a directory for new PDF files
def watch_directory(input_dir, parameters):
    cp.blue("\nWatching for PDF files in \"" + input_dir + "\"...")
    event_handler = PDFFileHandler(input_dir, parameters)
    observer = Observer()
    observer.schedule(event_handler, input_dir, recursive=False)
    observer.start()

    try:
        while True:
            sleep(1)
    except KeyboardInterrupt:
        observer.stop()  # Stop the file system watcher if interrupted by the user

    observer.join()

# Convert a dictionary to a list of lists
def dict_to_list_of_lists(data):
    result = []
    for item in data:
        result.append(list(item.values()))
    return result

#############################################################################
############################# Main Script ###################################
#############################################################################

qualer_parameter_sets = dict_to_list_of_lists(CONFIG)

# Process pre-existing PDF files
for qualer_parameters in qualer_parameter_sets:
    move_old_pdfs(qualer_parameters[1], DELETE_MODE) # Check for and move PDFs in the archive directory not created today
    move_old_pdfs(qualer_parameters[2], DELETE_MODE) # Check for and move PDFs in the reject directory not created today
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
