# app/api.py

import json
import os.path as path
import traceback

import requests

import app.color_print as cp
import app.pdf as pdf
from config import *
from urllib3.exceptions import MaxRetryError

ERROR_FLAG = "ERROR:"


def handle_error(response):
    cp.red(ERROR_FLAG)
    cp.red("STATUS CODE:" + str(response.status_code))
    cp.red("RESPONSE:" + response.text)
    return


def handle_exception(exception, response=None):
    cp.red(ERROR_FLAG)
    if response is not None:
        cp.red("STATUS CODE:" + str(response.status_code))
        cp.red("RESPONSE:" + response.text)
    cp.red("EXCEPTION: " + str(exception))
    traceback.print_exc()
    return


def login(endpoint, username, password):
    endpoint = endpoint + '/login'

    header = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    data = {
        "UserName": username,
        "Password": password,
        "ClearPreviousTokens": "False"
    }
    try:
        with requests.post(endpoint, data=json.dumps(data), headers=header) as r:
            if r.status_code != 200:
                handle_error(r)

            try:
                response = json.loads(r.text)
                token = response['Token']
                cp.green("Api-Token " + token)
                return token
            except Exception as e:
                handle_exception(e, r)

    except MaxRetryError:
        print("Is the internet down?")


def get_service_orders(data, token):
    endpoint = QUALER_ENDPOINT + '/service/workorders'
    header = {
        "Authorization": "Api-Token " + token,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    with requests.get(endpoint, params=data, headers=header) as r:
        if r.status_code != 200:
            handle_error(r)
        response = json.loads(r.text)
        print(str(len(response)) + " service orders found.")
        return response


def getServiceOrderId(endpoint, token, workOrderNumber):
    print("Fetching service order id for work order: " + workOrderNumber + "...")
    data = {"workOrderNumber": workOrderNumber}
    try:
        response = get_service_orders(data, token)
        # comes as a list, so return ServiceOrderId from first element
        return response[0]['ServiceOrderId']
    except Exception as e:
        handle_exception(e, response)


def upload(endpoint, token, filepath, serviceOrderId, qualertype):
    print("Attempting upload: SO# " + str(serviceOrderId) + " - " + path.basename(filepath))

    # https://requests.readthedocs.io/en/latest/user/quickstart/#post-a-multipart-encoded-file

    endpoint = endpoint + '/service/workorders/' + str(serviceOrderId) + '/documents'

    if not path.exists(filepath):
        cp.red(ERROR_FLAG)
        cp.red(filepath + " does not exist")
        return False
    attempts = 0

    while attempts < 5:
        if attempts > 0:
            new_filename = pdf.increment_filename(filepath)
            pdf.try_rename(filepath, new_filename)
            filepath = new_filename
        with open(filepath, 'rb') as file:
            files = {'file': file}

            headers = {
                "Authorization": "Api-Token " + token,
                "Accept": "application/json",
                "Content-Length": str(path.getsize(filepath))
            }

            requestData = {
                'model.reportType': qualertype,
            }
            if attempts > 0:
                cp.yellow("Retrying upload...")
            with requests.post(endpoint, params=requestData, headers=headers, files=files) as r:
                if r.status_code == 200:
                    cp.green("Upload successful!")
                    return True, filepath

                try:
                    response_data = json.loads(r.text)
                    error_message = response_data.get("Message", "")
                except Exception as e:
                    handle_exception(e, r)

                if r.status_code == 400 and error_message == "This document version is locked and cannot be overwritten.":
                    cp.yellow(error_message)
                    attempts += 1
                    # No return, so that we can try again after the file is renamed.
                else:  # if r.status_code != 200
                    handle_error(r)
                    return False, filepath


# Function to get a list of documents for a service order
def get_service_order_document_list(endpoint, token, ServiceOrderId):
    print("Fetching document list for service order: " + str(ServiceOrderId) + "...")

    headers = {
        'Accept': 'application/json',
        'Authorization': 'Api-Token ' + token
    }

    endpoint = endpoint + "/service/workorders/documents/list"

    data = {
        "from": "1900-01-01T00:00:00",
        "to": "2500-01-01T00:00:00",
        "serviceOrderId": ServiceOrderId
    }

    with requests.get(endpoint, params=data, headers=headers) as r:
        if r.status_code != 200:
            handle_error(r)

        try:
            data = json.loads(r.text)
            file_names = []
            for item in data:
                file_names.append(item["FileName"])
            print("Found " + str(len(file_names)) + " documents for service order: " + str(ServiceOrderId))
            return file_names
        except Exception as e:
            handle_exception(e, r)
