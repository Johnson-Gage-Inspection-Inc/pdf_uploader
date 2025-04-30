"""
upload.py

!/bin/python3

dependencies (linux):
sudo apt install poppler-utils
sudo apt install tesseract-ocr (or, install windows tesseract)

windows/linux
pip3 install PyPDF2 pytesseract requests pypdfium2
"""

from datetime import datetime
import os
import sys
import traceback
from typing import Tuple
import app.color_print as cp
from app.PurchaseOrders import update_PO_numbers, extract_po
import app.api as api
import app.pdf as pdf
from app.config import QUALER_STAGING_ENDPOINT, DEBUG, LIVEAPI, QUALER_ENDPOINT, LOG_FILE
from dotenv import load_dotenv
from app.orientation import reorient_pdf_for_workorders
import logging

try:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        filename=LOG_FILE,
        filemode="a",
    )
except FileNotFoundError:
    text = f"Log file not found: {LOG_FILE}"
    logging.critical(text)
    print(text)
    input("Press Enter to exit...")
    raise SystemExit


def get_credentials():
    """Retrieve credentials from environment variables."""
    username = os.environ.get("QUALER_EMAIL")
    password = os.environ.get("QUALER_PASSWORD")
    return (username, password) if username and password else None


def getEnv():
    # Try to load from environment variables first (useful for CI/CD)
    if creds := get_credentials():
        return creds

    # If not found, try loading from .env file
    base_path = (
        sys._MEIPASS if getattr(sys, "frozen", False) else os.path.dirname(__file__)
    )
    dotenv_path = os.path.join(base_path, ".env")
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)
        if creds := get_credentials():
            return creds

    raise ValueError("Credentials not found in environment or .env file")


# Rename File
def rename_file(filepath: str, doc_list: list) -> str:
    try:
        cp.yellow("File already exists in Qualer. Renaming file...")
        file_name = os.path.basename(filepath)
        attempts = 10
        did_rename = False
        new_filepath = filepath
        # Try to rename the file up to 10 times
        while not did_rename and attempts > 0:
            # Increment the filename
            new_filepath = pdf.increment_filename(new_filepath)
            new_filename = os.path.basename(new_filepath)
            # If the file does not exist in Qualer, upload it
            if (new_filename not in doc_list):
                # Try to rename the file
                did_rename = pdf.try_rename(filepath, new_filepath)
            attempts -= 1
        cp.green(f"'{file_name}' renamed to: '{new_filename}'")
        return new_filepath
    except FileNotFoundError:
        raise
    except Exception as e:
        cp.red(f"Error in rename_file(): {e} \nFile: {filepath}")
        traceback.print_exc()
        return filepath


def upload_with_rename(
    filepath: str, serviceOrderId: str, doc_type: str
) -> Tuple[bool, str]:
    """Upload file to Qualer endpoint, and resolve name conflicts"""
    file_name = os.path.basename(filepath)  # Get file name
    doc_list = api.get_service_order_document_list(
        QUALER_ENDPOINT, token, serviceOrderId
    )  # get list of documents for the service order
    new_filepath = (
        rename_file(filepath, doc_list) if file_name in doc_list else filepath
    )  # if the file already exists in Qualer, rename it
    try:
        if DEBUG:
            cp.yellow("debug mode, no uploads")
        uploadResult, new_filepath = api.upload(token, new_filepath, serviceOrderId, doc_type)
    except FileExistsError:
        cp.red(f"File exists in Qualer: {file_name}")
        uploadResult = False, filepath
    return uploadResult, new_filepath


# Get service order ID and upload file to Qualer endpoint
def fetch_SO_and_upload(workorder: str, filepath: str, QUALER_DOCUMENT_TYPE: str):
    try:
        if not os.path.isfile(filepath):  # See if filepath is valid
            return False, filepath
        if serviceOrderId := api.getServiceOrderId(token, workorder):
            return upload_with_rename(
                filepath, serviceOrderId, QUALER_DOCUMENT_TYPE
            )  # return uploadResult, new_filepath
        else:
            cp.red(f"Service order not found for work order: {workorder}")
            return False, filepath
    except FileNotFoundError as e:
        cp.red(f"Error: {filepath} not found.\n{e}")
        return False, filepath
    except Exception as e:
        cp.red(f"Error in fetch_SO_and_upload(): {e}\nFile: {filepath}")
        traceback.print_exc()
        return False, filepath


# Get service order ID and upload file to Qualer endpoint
def upload_by_po(
    filepath: str, po: str, dict: dict, QUALER_DOCUMENT_TYPE: str
) -> Tuple[list, list, str]:
    if po not in dict:
        cp.yellow(f"PO# {po} not found in Qualer.")
        return [], [], filepath
    serviceOrderIds = dict[po]
    cp.green(f"Found {len(serviceOrderIds)} service orders for PO {po}: {serviceOrderIds}")
    successSOs = []
    failedSOs = []
    for serviceOrderId in serviceOrderIds:
        try:
            if not os.path.isfile(filepath):
                return [], serviceOrderIds, filepath
            uploadResult, filepath = upload_with_rename(
                filepath, serviceOrderId, QUALER_DOCUMENT_TYPE
            )  # return uploadResult, new_filepath
            if uploadResult:
                successSOs.append(serviceOrderId)
            else:
                failedSOs.append(serviceOrderId)
        except FileNotFoundError as e:
            cp.red(f"Error: {filepath} not found.\n{e}")
            return [], serviceOrderIds, filepath
        except FileExistsError:
            cp.red(f"File exists in Qualer: {os.path.basename(filepath)}")
            return [], serviceOrderIds, filepath
        except Exception as e:
            cp.red(f"Error in fetch_SO_and_upload(): {e} \nFile: {filepath}")
            traceback.print_exc()
            return [], serviceOrderIds, filepath
    return successSOs, failedSOs, filepath


# Main function
def process_file(filepath: str, qualer_parameters: tuple):
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    cp.blue(f"Processing file: {filepath}")
    # unpack parameters
    INPUT_DIR, OUTPUT_DIR, REJECT_DIR, QUALER_DOCUMENT_TYPE = qualer_parameters

    global noworkorders
    global total
    new_filepath = False
    total += 1
    filename = os.path.basename(filepath)
    uploadResult = False

    # Check for PO in file name
    if filename.startswith("PO"):
        uploadResult = handle_po_upload(filepath, QUALER_DOCUMENT_TYPE, filename)

    if not uploadResult:
        # Check for work orders in file body or file name
        workorders = pdf.workorders(filepath) or reorient_pdf_for_workorders(filepath, REJECT_DIR)
        if not workorders:
            return False

        # if work orders found in filename, upload file to Qualer endpoint(s)
        if isinstance(workorders, list):
            cp.green(
                f"Work order(s) found in file name: {workorders}"
            )  # Print the work order numbers
            for workorder in workorders:  # loop through work orders list and upload
                uploadResult, new_filepath = fetch_SO_and_upload(
                    workorder, filepath, QUALER_DOCUMENT_TYPE
                )  # upload file

        elif (
            len(workorders) == 1
        ):  # One work order was found in the file body (dict object of length 1)
            workorder = list(workorders.keys())[0]  # Get the work order number
            cp.green(
                f"One (1) work order found within file: {workorder}"
            )  # Print the work order number
            uploadResult, new_filepath = fetch_SO_and_upload(
                workorder, filepath, QUALER_DOCUMENT_TYPE
            )  # Upload the file

        else:  # For multiple work orders,
            cp.green(
                f"Multiple work orders found within file: {workorders}"
            )  # Print the work order numbers
            for (
                workorder,
                pg_nums,
            ) in workorders.items():  # loop through the workorders dict object,
                now = datetime.now().strftime(
                    "%Y%m%dT%H%M%S"
                )  # get the current date and time,
                child_pdf_path = f"{INPUT_DIR}/scanned_doc_{workorder}_{now}.pdf"
                pdf.create_child_pdf(
                    filepath, pg_nums, child_pdf_path
                )  # extract relevant pages from PDF, and
                uploadResult, new_child_pdf_path = fetch_SO_and_upload(
                    workorder, child_pdf_path, QUALER_DOCUMENT_TYPE
                )  # upload extracted pages
                child_pdf_path = (
                    new_child_pdf_path if new_child_pdf_path else child_pdf_path
                )  # if the file was renamed, update the filepath
                try:
                    # Remove child files after upload
                    (
                        os.remove(child_pdf_path)
                        if uploadResult
                        else cp.red(f"Failed to upload and remove {child_pdf_path}")
                    )
                except Exception as e:
                    cp.red(e)

    # If the upload still failed, move the file to the reject directory
    if not uploadResult and os.path.isfile(filepath):
        cp.red("Failed to upload " + filepath + ". Moving to reject directory...")
        pdf.move_file(filepath, REJECT_DIR)
        return False

    # If the file was renamed, update the filepath
    if new_filepath:
        filepath = new_filepath

    # Remove file if there were no failures
    # (if there were any failures, file will remain)
    try:
        if filepath and (OUTPUT_DIR is None or OUTPUT_DIR == ""):
            os.remove(filepath)
        elif filepath:
            # Archive only version:
            try:
                # Try moving the file to the archive folder
                pdf.move_file(filepath, OUTPUT_DIR)
            except FileExistsError:
                # Resolve naming conflict in the Archives folder
                new_filepath = filepath
                file_was_moved = False
                while not file_was_moved:
                    new_filepath = pdf.increment_filename(new_filepath)
                    file_was_moved = pdf.move_file(new_filepath, OUTPUT_DIR)
            except Exception as e:
                cp.red(e)
                traceback.print_exc()
                input("Press Enter to continue...")
        else:
            # If there was an upload failure, increment the filename and try again
            os.rename(filepath, pdf.increment_filename(filepath))

    except Exception as e:
        cp.yellow("Failed to remove file:", filepath, e)
        logging.debug(traceback.format_exc())


def handle_po_upload(filepath, QUALER_DOCUMENT_TYPE, filename):
    po = extract_po(filename)
    po_dict = update_PO_numbers(token)
    cp.white("PO found in file name: " + po)
    successSOs, failedSOs, new_filepath = upload_by_po(
            filepath, po, po_dict, QUALER_DOCUMENT_TYPE
        )
    uploadResult = False
    if successSOs:
        cp.green(f"{filename} uploaded successfully to SOs: {successSOs}")
        uploadResult = True
    if failedSOs:
        cp.red(f"{filename} failed to upload to SOs: {failedSOs}")
    return uploadResult


if not LIVEAPI:
    QUALER_ENDPOINT = QUALER_STAGING_ENDPOINT  # noqa: F811
    cp.yellow("Using staging API")

username, password = getEnv()
token = api.login(QUALER_ENDPOINT, username, password)

total = 0
