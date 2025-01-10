#
import datetime as dt
import gzip
import json
import os
import app.api as api
import app.color_print as cp

DT_FORMAT = "%Y-%m-%dT%H:%M:%S"


def update_dict(dict: dict, response: list) -> dict:
    for so in response:
        PrimaryPo = so['PoNumber']
        SecondaryPo = so['SecondaryPo']
        ServiceOrderId = so['ServiceOrderId']
        if PrimaryPo not in dict:
            dict[PrimaryPo] = [ServiceOrderId]
        elif ServiceOrderId not in dict[PrimaryPo]:
            dict[PrimaryPo].append(ServiceOrderId)
        if SecondaryPo not in dict[PrimaryPo]:
            dict[SecondaryPo] = [ServiceOrderId]
        elif ServiceOrderId not in dict[SecondaryPo]:
            dict[SecondaryPo].append(ServiceOrderId)
    return dict


def _get_PO_numbers(token: str, start_str="2020-08-13T00:00:00", end_str=dt.datetime.now().strftime(DT_FORMAT), increment=91):
    """ Get a dictionary of PO numbers and their corresponding service order IDs from the API.

    Args:
        token (str): The API token.
        start_str (str, optional): Start date for PO search. Format: "%Y-%m-%dT%H:%M:%S". Defaults to "2020-08-13T00:00:00".
        end_str (str, optional): End date for PO search. Format: "%Y-%m-%dT%H:%M:%S". Defaults to dt.datetime.now().strftime(DT_FORMAT).
        increment (int, optional): Number of days to search at a time. Defaults to 91.

    Returns:
        dict: A dictionary of PO numbers and their corresponding service order IDs.
    """
    dict = {}

    start_date = dt.datetime.strptime(start_str, DT_FORMAT)
    end_date = dt.datetime.strptime(end_str, DT_FORMAT)

    from_date = start_date
    to_date = from_date + dt.timedelta(days=increment)

    while True:
        cp.white(f"Getting service orders from {from_date.strftime(DT_FORMAT)} to {to_date.strftime(DT_FORMAT)}...")
        data = {
            'from': from_date.strftime(DT_FORMAT),
            'to': to_date.strftime(DT_FORMAT)
        }  # Set the parameters for the API call
        response = api.get_service_orders(data, token)
        dict = update_dict(dict, response)
        if to_date > end_date:
            break
        from_date = to_date
        to_date = from_date + dt.timedelta(days=increment)
    print("Done.")
    return dict


def update_PO_numbers(token: str, file_path: str = 'app/dict.json.gz', modified_after: str = None) -> dict:
    """ Update the PO dictionary with new PO numbers from the API.

    Args:
        file_path (str): File path for the PO dictionary.
        token (str): The API token.
        modified_after (str, optional): Only get service orders modified after this date. Format: "%Y-%m-%dT%H:%M:%S". Defaults to None.

    Returns:
        dict: A dictionary of PO numbers and their corresponding service order IDs.
    """
    # Read the compressed dictionary from the file
    try:
        dict = expand_from_file()
    except gzip.BadGzipFile:
        dict = _get_PO_numbers(token)
        save_as_zip_file(dict)
    except FileNotFoundError:
        raise

    current_datetime = dt.datetime.now()                                    # Get the current datetime

    timestamp = os.path.getmtime(file_path)                                 # Get the timestamp of the last modification
    last_modified = dt.datetime.fromtimestamp(timestamp)                    # Convert the timestamp to a datetime object

    if modified_after is None:
        modified_after = last_modified.strftime(DT_FORMAT)

    # Check if the file has been modified since the last update
    if last_modified < current_datetime:
        data = {'modifiedAfter': modified_after}
        response = api.get_service_orders(data, token)
        if len(response) > 0:
            dict = update_dict(dict, response)
            save_as_zip_file(file_path, dict)  # Compress the updated dictionary and write to the file
            cp.white(f"Dictionary updated and saved to {file_path}.")
            return dict
    cp.white("No changes detected since the last update.")
    return dict


def save_as_zip_file(dict: dict, file_path: str = 'app/dict.json.gz'):
    """ Compress the dictionary and write to the file.

    Args:
        file_path (str): File path for the PO dictionary.
        dict (dict): A dictionary of PO numbers and their corresponding service order IDs.
    """
    with gzip.open(file_path, 'wb') as file:
        json_data = json.dumps(dict).encode('utf-8')
        file.write(json_data)


def expand_from_file(file_path: str = 'app/dict.json.gz'):
    """ Read the compressed dictionary from the file.

    Args:
        file_path (str): File path for the PO dictionary.

    Returns:
        dict: A dictionary of PO numbers and their corresponding service order IDs.
    """
    with gzip.open(file_path, 'rb') as file:
        json_data = file.read()
        dict = json.loads(json_data.decode('utf-8'))
    return dict


def extract_po(filename: str) -> str:
    """ Extract the PO number from the filename.

    Args:
        filename (str): The filename.

    Returns:
        str: The PO number.
    """
    possible_delimiters = [" ", "_", "-", "#"]
    po = filename.replace(' - ', '-')
    for delimiter in possible_delimiters:
        if filename.startswith("PO" + delimiter):
            po = po.replace(".pdf", "").split(delimiter)[1]
            return po
    if filename.startswith("PO"):
        for delimiter in possible_delimiters:
            possible_po = po.replace(".pdf", "").split(delimiter)[0].replace("PO", "")
            if len(possible_po) < len(po):
                po = possible_po
    return po
