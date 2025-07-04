# PurchaseOrders.py
import datetime as dt
import gzip
import json
import os
import app.api as api
import app.color_print as cp
from app.config import PO_DICT_FILE
import re

DT_FORMAT = "%Y-%m-%dT%H:%M:%S"


def update_dict(lookup: dict, response: list) -> dict:
    for so in response:
        PrimaryPo = so["PoNumber"]
        SecondaryPo = so["SecondaryPo"]
        ServiceOrderId = so["ServiceOrderId"]
        if PrimaryPo not in lookup:
            lookup[PrimaryPo] = [ServiceOrderId]
        elif ServiceOrderId not in lookup[PrimaryPo]:
            lookup[PrimaryPo].append(ServiceOrderId)
        if SecondaryPo not in lookup[PrimaryPo]:
            lookup[SecondaryPo] = [ServiceOrderId]
        elif ServiceOrderId not in lookup[SecondaryPo]:
            lookup[SecondaryPo].append(ServiceOrderId)
    return lookup


def _get_PO_numbers(
    token: str,
    start_str="2020-08-13T00:00:00",
    end_str=dt.datetime.now().strftime(DT_FORMAT),
    increment=91,
) -> dict:
    """Get a dictionary of PO numbers and their corresponding service order IDs from the API.

    Args:
        token (str): The API token.
        start_str (str, optional): Start date for PO search.
            Format: "%Y-%m-%dT%H:%M:%S". Defaults to "2020-08-13T00:00:00".
        end_str (str, optional): End date for PO search.
            Format: "%Y-%m-%dT%H:%M:%S". Defaults to dt.datetime.now().strftime(DT_FORMAT).
        increment (int, optional): Number of days to search at a time. Defaults to 91.

    Returns:
        lookup (dict): PO numbers and their corresponding service order IDs.
    """
    lookup = {}

    start_date = dt.datetime.strptime(start_str, DT_FORMAT)
    end_date = dt.datetime.strptime(end_str, DT_FORMAT)

    from_date = start_date
    to_date = from_date + dt.timedelta(days=increment)

    while True:
        cp.white(
            f"Getting service orders from {from_date.strftime(DT_FORMAT)} to {to_date.strftime(DT_FORMAT)}..."
        )
        data = {
            "from": from_date.strftime(DT_FORMAT),
            "to": to_date.strftime(DT_FORMAT),
        }  # Set the parameters for the API call
        response = api.get_service_orders(data, token)
        lookup = update_dict(lookup, response)
        if to_date > end_date:
            break
        from_date = to_date
        to_date = from_date + dt.timedelta(days=increment)
    print("Done.")
    return lookup


def update_PO_numbers(
    token: str, modified_after: str = None
) -> dict:
    """Update the PO dictionary with new PO numbers from the API.

    Args:
        token (str): The API token.
        modified_after (str, optional): Only get service orders modified after this date.
            Format: "%Y-%m-%dT%H:%M:%S". Defaults to None.

    Returns:
        lookup (dict): PO numbers and their corresponding service order IDs.
    """
    # Read the compressed dictionary from the file
    try:
        with gzip.open(PO_DICT_FILE, "rb") as f:
            lookup = json.loads(f.read().decode("utf-8"))
        cp.green(f"Using PO dictionary file at: {PO_DICT_FILE}")
    except gzip.BadGzipFile:
        cp.red("Error: The file is not a valid gzip file.")
        lookup = _get_PO_numbers(token)
        save_as_zip_file(lookup, PO_DICT_FILE)

    timestamp = os.path.getmtime(PO_DICT_FILE)  # Get the time of the last change
    last_modified = dt.datetime.fromtimestamp(timestamp)

    # Check if the file has been modified since the last update
    if last_modified < dt.datetime.now():
        if modified_after is None:
            modified_after = last_modified.strftime(DT_FORMAT)
        data = {"modifiedAfter": modified_after}
        response = api.get_service_orders(data, token)
        if len(response) > 0:
            cp.yellow(f"Saving dictionary to {os.path.relpath(PO_DICT_FILE)}...")
            lookup = update_dict(lookup, response)
            save_as_zip_file(lookup)
            cp.white(f"Dictionary updated and saved to {PO_DICT_FILE}.")
            return lookup
    cp.white("No changes detected since the last update.")
    return lookup


def save_as_zip_file(lookup: dict):
    """Compress the dictionary and write to the file.

    Args:
        lookup (dict): PO numbers and their corresponding service order IDs.
    """
    with gzip.open(PO_DICT_FILE, "wb") as file:
        json_data = json.dumps(lookup).encode("utf-8")
        file.write(json_data)


def extract_po(filename: str) -> str:
    """Extract the PO number from the filename using regular expressions.

    The filename is expected to start with 'PO' optionally followed by delimiters
    such as space, underscore, dash, or hash, then the PO number.

    Args:
        filename (str): The filename.

    Returns:
        str: The extracted PO number.
    """
    # Remove .pdf extension properly if present.
    if filename.lower().endswith(".pdf"):
        filename = filename.replace(" - ", "-")[:-4]
    else:
        raise ValueError("Filename must end with .pdf")
    # Match "PO" followed by optional delimiters then capture the PO number.
    if match := re.match(r"^PO[\s_\-#]*(\S+)", filename, flags=re.IGNORECASE):
        return match.group(1)
    return filename
