# app/file_ops.py -- File system operations (move, rename, increment filename).

import os
from time import sleep
from traceback import print_exc

import app.color_print as cp


def increment_filename(old_filename) -> str:
    """Increment a filename's numeric suffix, e.g. file.pdf -> file (1).pdf."""
    for i in range(99, 0, -1):
        old_suffix = f" ({i}).pdf"
        new_suffix = f" ({i + 1}).pdf"
        new_filename = old_filename.replace(old_suffix, new_suffix)
        if new_filename != old_filename:
            break
    else:
        new_filename = old_filename.replace(".pdf", " (1).pdf")
    sleep(1)  # Wait 1 second before renaming
    return new_filename


def move_file(filepath, output_dir) -> tuple[str, bool]:
    """Move a file to the given directory, retrying on transient errors."""
    file_name = os.path.basename(filepath)
    new_filepath = os.path.join(output_dir, file_name)
    attempt = 0
    while attempt < 50:  # Max number of rename attempts = 50
        try:
            os.rename(filepath, new_filepath)
            cp.green(f"Moved file to {os.path.relpath(new_filepath)}.")
            return new_filepath, True
        except PermissionError as e:
            cp.yellow(e)
            attempt += 1
            sleep(1)  # Wait 1 second before retrying
        except FileExistsError:
            if attempt == 0:
                print("Incrementing filename...", end="")
            else:
                print(".", end="")
            print()
            new_filepath = increment_filename(new_filepath)
            attempt += 1
        except FileNotFoundError as e:
            # This probably means the file was already moved by another process
            # (Perhaps another instance of this script is running?)
            cp.red(e)
            return "", False  # File not found, no need to retry
        except Exception as e:
            cp.red("Unexpected exception for " + filepath)
            cp.red(f"Failed to move {filepath} to {new_filepath}.")
            cp.red(e)
            print_exc()
            return "", False

    # If all rename attempts failed, handle the error
    cp.red(f"Failed to move file to the reject directory: {filepath}")
    return "", False


def try_rename(src_path, dst_path, retries=5, delay=2) -> bool:
    """Rename a file, retrying on transient errors (e.g. OneDrive sync locks)."""
    for attempt in range(retries):
        try:
            os.rename(src_path, dst_path)
            return True
        except FileExistsError:
            return False
        except (FileNotFoundError, PermissionError, OSError) as e:
            if attempt < retries - 1:
                cp.yellow(
                    f"Rename attempt {attempt + 1}/{retries} failed: {e}. Retrying in {delay}s..."
                )
                sleep(delay)
            else:
                cp.red(f"Failed to rename file after {retries} attempts: {e}")
                raise
    return False
