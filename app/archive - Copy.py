# app/archive.py

import os
import shutil
import time


def move_old_pdfs(folder, delete_mode=False):
    print(f"Checking \"{folder}\" for PDFs from before today...")
    # In archive mode, create the "Old Files" subfolder if it doesn't exist
    subfolder = os.path.join(folder, "Old PDFs")
    if not os.path.exists(subfolder) and not delete_mode:
        os.makedirs(subfolder)

    # Get the current date
    current_date = time.strftime("%Y-%m-%d")

    # Get a list of all files in the folder
    pdf_files = [f for f in os.listdir(folder) if f.endswith(".pdf")]

    for file in pdf_files:
        file_path = os.path.join(folder, file)

        # Get the file's creation time
        creation_time = os.path.getctime(file_path)

        # Convert the creation time to a formatted date
        file_date = time.strftime("%Y-%m-%d", time.localtime(creation_time))

        # If the file was not created today, move or delete it based on the mode
        if file_date != current_date:
            if delete_mode:
                try:
                    os.remove(file_path)
                    print(f"Deleted {file}.")
                except OSError as e:
                    print(f"Error deleting {file}: {str(e)}")
            else:
                destination_path = os.path.join(subfolder, file)

                try:
                    shutil.move(file_path, destination_path)
                    print(f"Moved {file} to Old Files subfolder.")
                except shutil.Error as e:
                    print(f"Error moving {file}: {str(e)}")
                    # If there's a naming conflict, delete the file instead of moving it
                    os.remove(file_path)
                    print(f"Could not move {file}. File deleted instead.")
                except OSError as e:
                    print(f"Error moving {file}: {str(e)} (File in use)")

