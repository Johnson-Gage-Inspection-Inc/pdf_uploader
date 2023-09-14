import os
import shutil
import time
import zipfile

def move_old_pdfs(folder, delete_mode=False):
    print(f"Checking \"{folder}\" for PDFs from before today...")

    # Get the current date
    current_date = time.strftime("%Y-%m-%d")

    # Get a list of all files in the folder
    pdf_files = [f for f in os.listdir(folder) if f.endswith(".pdf")]

    compressed = 0

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
                try:
                    # Create a zip folder
                    zip_path = os.path.join(folder, "Archive.zip")
                    with zipfile.ZipFile(zip_path, "a", zipfile.ZIP_DEFLATED) as zipf:
                        zipf.write(file_path, file)

                    # Remove the original file
                    os.remove(file_path)
                    compressed += 1
                except shutil.Error as e:
                    print(f"Error compressing and moving {file}: {str(e)}")
                except OSError as e:
                    print(f"Error compressing and moving {file}: {str(e)} (File in use)")
    print(f"Compressed {str(compressed)} files in {folder}.")
