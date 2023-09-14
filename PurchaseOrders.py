import datetime as dt
import gzip
import json
import os

import app.api as api
from config import *

dt_format = "%Y-%m-%dT%H:%M:%S"

def update_dict(dict, response):
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

def _get_PO_numbers(token, start_str="2020-08-13T00:00:00", end_str=dt.datetime.now().strftime(dt_format), increment=91):
    dict = {}

    start_date = dt.datetime.strptime(start_str, dt_format)
    end_date = dt.datetime.strptime(end_str, dt_format)

    from_date = start_date
    to_date = from_date + dt.timedelta(days=increment)

    while True:
        print("Getting service orders from " + from_date.strftime(dt_format) + " to " + to_date.strftime(dt_format) + "...")
        data = {
            'from': from_date.strftime(dt_format),
            'to': to_date.strftime(dt_format)
        }  # Set the parameters for the API call
        response = api.get_service_orders(data, token)
        dict = update_dict(dict, response)
        if to_date > end_date:
            break
        from_date = to_date
        to_date = from_date + dt.timedelta(days=increment)
    print("Done.")
    return dict

def update_PO_numbers(file_path, token, modified_after = None):
    # Read the compressed dictionary from the file
    dict = expand_from_file(file_path)
        
    current_datetime = dt.datetime.now()                                    # Get the current datetime

    timestamp = os.path.getmtime(file_path)                                 # Get the timestamp of the last modification
    last_modified = dt.datetime.fromtimestamp(timestamp)                    # Convert the timestamp to a datetime object

    if modified_after is None:
        modified_after = last_modified.strftime(dt_format)

    # Check if the file has been modified since the last update
    if last_modified < current_datetime:
        data = {'modifiedAfter': modified_after}
        response = api.get_service_orders(data, token)
        if len(response) > 0:
            dict = update_dict(dict, response)
            save_as_zip_file(file_path, dict) # Compress the updated dictionary and write to the file
            print("Dictionary updated and saved to", file_path)
            return dict
    print("No changes detected since the last update.")
    return dict

def save_as_zip_file(file_path, dict):
    with gzip.open(file_path, 'wb') as file:
        json_data = json.dumps(dict).encode('utf-8')
        file.write(json_data)

def expand_from_file(file_path):
    with gzip.open(file_path, 'rb') as file:
        json_data = file.read()
        dict = json.loads(json_data.decode('utf-8'))
    return dict

def extract_po(filename):
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

# Set the file path for the PO dictionary
if os.path.exists('app'):
    file_path = 'app/dict.json.gz' # Local path
else:
    file_path = 'C:\\uploader\\app\\dict.json.gz' # Server path
