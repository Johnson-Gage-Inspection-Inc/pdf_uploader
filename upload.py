"""
upload.py

!/bin/python3

dependencies (linux):
sudo apt install poppler-utils
sudo apt install tesseract-ocr (or, install windows tesseract)

windows/linux
pip3 install -r requirements.txt  # includes PyPDF2, pytesseract, pypdfium2, qualer_sdk from git
"""

from datetime import datetime
import os
import traceback
from typing import Tuple
import app.color_print as cp
from app.PurchaseOrders import update_PO_numbers, extract_po
import app.api as api
import app.pdf as pdf
from app.config import (
    DEBUG,
    LIVEAPI,
    LOG_FILE,
)
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
            if new_filename not in doc_list:
                # Try to rename the file
                did_rename = pdf.try_rename(filepath, new_filepath)
            attempts -= 1
        if not did_rename:
            cp.red(f"Failed to rename '{file_name}' after multiple attempts.")
            return filepath
        cp.green(f"'{file_name}' renamed to: '{new_filename}'")
        return new_filepath
    except FileNotFoundError:
        raise
    except Exception as e:
        cp.red(f"Error in rename_file(): {e} \nFile: {filepath}")
        traceback.print_exc()
        return filepath


def upload_with_rename(
    filepath: str, serviceOrderId: int, doc_type: str
) -> Tuple[bool, str]:
    """Upload file to Qualer endpoint, and resolve name conflicts"""
    file_name = os.path.basename(filepath)  # Get file name
    doc_list = api.get_service_order_document_list(
        serviceOrderId
    )  # get list of documents for the service order
    if doc_list is None:
        doc_list = []
    new_filepath = (
        rename_file(filepath, doc_list) if file_name in doc_list else filepath
    )  # if the file already exists in Qualer, rename it
    try:
        if DEBUG:
            cp.yellow("debug mode, no uploads")
            # Skip actual upload in debug mode to avoid network/API calls
            return False, new_filepath
        uploadResult, new_filepath = api.upload(new_filepath, serviceOrderId, doc_type)
    except FileExistsError:
        cp.red(f"File exists in Qualer: {file_name}")
        uploadResult = False
    return uploadResult, new_filepath


# Get service order ID and upload file to Qualer endpoint
def fetch_SO_and_upload(workorder: str, filepath: str, QUALER_DOCUMENT_TYPE: str):
    try:
        if not os.path.isfile(filepath):  # See if filepath is valid
            return False, filepath
        if serviceOrderId := api.getServiceOrderId(workorder):
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
    filepath: str, po: str, po_dict: dict, QUALER_DOCUMENT_TYPE: str
) -> Tuple[list, list, str]:
    if po not in po_dict:
        cp.yellow(f"PO# {po} not found in Qualer.")
        return [], [], filepath
    serviceOrderIds = po_dict[po]
    cp.green(
        f"Found {len(serviceOrderIds)} service orders for PO {po}: {serviceOrderIds}"
    )
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

    global total
    new_filepath: str | bool = False
    total += 1
    filename = os.path.basename(filepath)
    uploadResult = False

    # Check for PO in file name
    if filename.startswith("PO"):
        uploadResult, new_filepath = handle_po_upload(
            filepath, QUALER_DOCUMENT_TYPE, filename
        )

    if not uploadResult:
        # Check for work orders in file body or file name
        workorders_result: dict | list | bool = pdf.workorders(filepath)
        if not workorders_result:
            workorders_result = reorient_pdf_for_workorders(filepath, REJECT_DIR)
        if not workorders_result:
            return False

        # if work orders found in filename, upload file to Qualer endpoint(s)
        if isinstance(workorders_result, list):
            cp.green(
                f"Work order(s) found in file name: {workorders_result}"
            )  # Print the work order numbers
            for (
                workorder
            ) in workorders_result:  # loop through work orders list and upload
                uploadResult, new_filepath = fetch_SO_and_upload(
                    workorder, filepath, QUALER_DOCUMENT_TYPE
                )  # upload file

        elif isinstance(workorders_result, dict):
            if (
                len(workorders_result) == 1
            ):  # One work order was found in the file body (dict object of length 1)
                workorder = list(workorders_result.keys())[
                    0
                ]  # Get the work order number
                cp.green(
                    f"One (1) work order found within file: {workorder}"
                )  # Print the work order number
                uploadResult, new_filepath = fetch_SO_and_upload(
                    workorder, filepath, QUALER_DOCUMENT_TYPE
                )  # Upload the file

            else:  # For multiple work orders,
                cp.green(
                    f"Multiple work orders found within file: {workorders_result}"
                )  # Print the work order numbers
                for (
                    workorder,
                    pg_nums,
                ) in (
                    workorders_result.items()
                ):  # loop through the workorders dict object,
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
    if new_filepath is not False:
        if not isinstance(new_filepath, str):
            raise ValueError(
                f"Expected new_filepath to be a string, got {type(new_filepath)}"
            )
        filepath = new_filepath

    # Remove file if there were no failures
    # (if there were any failures, file will remain)
    try:
        if filepath and (OUTPUT_DIR is None or OUTPUT_DIR == ""):
            os.remove(filepath)
        elif filepath:
            # Archive only version:
            try:
                # Move the file to the archive folder.
                # move_file handles FileExistsError internally
                # by incrementing the destination filename.
                pdf.move_file(filepath, OUTPUT_DIR)
            except Exception as e:
                cp.red(e)
                traceback.print_exc()
                input("Press Enter to continue...")

    except Exception as e:
        cp.yellow(f"Failed to remove file: {filepath} | {e}")
        logging.debug(traceback.format_exc())


def handle_po_upload(filepath, QUALER_DOCUMENT_TYPE, filename):
    po = extract_po(filename)
    po_dict = update_PO_numbers()
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
    return uploadResult, new_filepath


if not LIVEAPI:
    cp.yellow("Using staging API")

total = 0
