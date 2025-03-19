# app/api.py

import json
from os import path
import traceback
import requests
import app.color_print as cp
import app.pdf as pdf
from app.config import *
from urllib3.exceptions import MaxRetryError
from app.connectivity import check_connectivity

ERROR_FLAG = "ERROR:"


def handle_error(response):
    cp.red(ERROR_FLAG)
    cp.red(f"STATUS CODE: {response.status_code}")
    cp.red(f"RESPONSE: {response.text}")
    return


def handle_exception(exception, response=None):
    cp.red(ERROR_FLAG)
    if isinstance(response, requests.Response):
        cp.red(f"STATUS CODE: {response.status_code}")
        cp.red(f"RESPONSE: {response.text}")
    elif response:
        cp.red(f"Invalid response passed: {response}")
    cp.red(f"EXCEPTION: {exception}")
    traceback.print_exc()


def login(endpoint, username, password):
    endpoint = endpoint + "/login"

    header = {"Content-Type": "application/json", "Accept": "application/json"}

    if not username or not password:
        cp.red(ERROR_FLAG)
        cp.red("Username or password not provided.")
        raise SystemExit

    data = {"UserName": username, "Password": password, "ClearPreviousTokens": "False"}
    try:
        with requests.post(endpoint, data=json.dumps(data), headers=header) as r:
            if r.status_code != 200:
                handle_error(r)

            try:
                response = json.loads(r.text)
                if token := response.get("Token"):
                    cp.green("Api-Token " + token)
                    return token
                else:
                    cp.red(ERROR_FLAG)
                    cp.red("No token found in response")
                    raise SystemExit
            except Exception as e:
                handle_exception(e, r)

    except MaxRetryError:
        check_connectivity()
        cp.red("Unable to connect to Qualer. Aborting...")
        raise SystemExit


def get_service_orders(data, token):
    endpoint = QUALER_ENDPOINT + "/service/workorders"
    header = {
        "Authorization": "Api-Token " + token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    with requests.get(endpoint, params=data, headers=header) as r:
        if r.status_code != 200:
            handle_error(r)
        response = json.loads(r.text)
        cp.white(f"{len(response)} service orders found.")
        return response


def getServiceOrderId(token: str, workOrderNumber: str) -> str:
    """Get the service order ID for a work order number.

    Args:
        token (str): API token
        workOrderNumber (str): Work order number

    Returns:
        str: _description_
    """
    cp.white("Fetching service order id for work order: " + workOrderNumber + "...")
    data = {"workOrderNumber": workOrderNumber}
    try:
        response = get_service_orders(data, token)
        # comes as a list, so return ServiceOrderId from first element
        if len(response) == 0:
            cp.red(ERROR_FLAG)
            cp.red(f"No service order found for work order: {workOrderNumber}")
            return False
        return response[0][
            "ServiceOrderId"
        ]  # Exception has occurred: IndexError (list index out of range)
    except Exception as e:
        handle_exception(e, response)


def upload(endpoint, token, filepath, serviceOrderId, qualertype):
    cp.white(f"Attempting upload for SO# {serviceOrderId}: '{path.basename(filepath)}'")

    # https://requests.readthedocs.io/en/latest/user/quickstart/#post-a-multipart-encoded-file

    endpoint = f"{endpoint}/service/workorders/{serviceOrderId}/documents"

    if not path.exists(filepath):
        cp.red(ERROR_FLAG)
        cp.red(f"{filepath} does not exist")
        return False
    attempts = 0

    while attempts < 5:
        if attempts > 0:
            new_filename = pdf.increment_filename(filepath)
            pdf.try_rename(filepath, new_filename)
            filepath = new_filename
        with open(filepath, "rb") as file:
            files = {"file": file}

            headers = {
                "Authorization": "Api-Token " + token,
                "Accept": "application/json",
                "Content-Length": str(path.getsize(filepath)),
            }

            requestData = {
                "model.reportType": qualertype,
            }
            if attempts > 0:
                cp.white("Retrying upload...")
            try:
                r = requests.post(
                    endpoint, params=requestData, headers=headers, files=files
                )

            except requests.exceptions.ReadTimeout as e:
                cp.yellow(e)
                attempts += 1
                continue

            if r.status_code == 200:
                cp.green("Upload successful!")
                return True, filepath

            try:
                response_data = json.loads(r.text)
                error_message = response_data.get("Message", "")
            except Exception as e:
                handle_exception(e, r)

            if (
                r.status_code == 400
                and error_message
                == "This document version is locked and cannot be overwritten."
            ):
                cp.yellow(error_message)
                attempts += 1
                # No return, so that we can try again after the file is renamed.
            else:  # if r.status_code != 200
                handle_error(r)
                return False, filepath


# Function to get a list of documents for a service order
def get_service_order_document_list(endpoint, token, ServiceOrderId):
    if not ServiceOrderId:
        cp.red(ERROR_FLAG)
        cp.red("ServiceOrderId not provided.")
        raise SystemExit

    cp.white(
        f"Fetching document list for service order: https://jgiquality.qualer.com/ServiceOrder/Info/{ServiceOrderId}..."
    )

    headers = {"Accept": "application/json", "Authorization": "Api-Token " + token}

    endpoint = endpoint + "/service/workorders/documents/list"

    params = {
        "from": "1900-01-01T00:00:00",
        "to": "2500-01-01T00:00:00",
        "serviceOrderId": ServiceOrderId,
    }

    with requests.get(endpoint, params=params, headers=headers) as r:
        if r.status_code != 200:
            handle_error(r)

        try:
            data = json.loads(r.text)
            file_names = []
            for item in data:
                file_names.append(item["FileName"])
            cp.white(
                f"Found {len(file_names)} documents for service order: https://jgiquality.qualer.com/ServiceOrder/Info/{ServiceOrderId}"
            )
            return file_names
        except Exception as e:
            handle_exception(e, r)
