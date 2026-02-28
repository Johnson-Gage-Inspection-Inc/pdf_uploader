# app/api.py

from os import path
import traceback
import httpx
import app.color_print as cp
import app.pdf as pdf
from app.connectivity import check_connectivity
from qualer_sdk.api.service_orders import get_work_orders
from qualer_sdk.api.service_order_documents import (
    get_documents_list,
    upload_documents_post_2,
)
from qualer_sdk.api.service_order_items import get_work_items as _sdk_get_work_items
from qualer_sdk.types import File
from typing import List, Optional
import json
from app.qualer_client import make_qualer_client

ERROR_FLAG = "ERROR:"


def handle_error(response: httpx.Response) -> None:
    cp.red(ERROR_FLAG)
    cp.red(f"STATUS CODE: {response.status_code}")
    cp.red(f"RESPONSE: {response.text}")
    return


def handle_exception(exception, response=None) -> None:
    cp.red(ERROR_FLAG)
    if isinstance(response, httpx.Response):
        cp.red(f"STATUS CODE: {response.status_code}")
        cp.red(f"RESPONSE: {response.text}")
    elif response is not None:
        cp.red(f"Invalid response passed: {response}")
    cp.red(f"EXCEPTION: {exception}")
    traceback.print_exc()


def get_service_orders(
    *,
    work_order_number: Optional[str] = None,
    from_: Optional[str] = None,
    to: Optional[str] = None,
    modified_after: Optional[str] = None,
    status: Optional[str] = None,
) -> list:
    """Fetch service orders from the Qualer API.

    Args:
        work_order_number: Filter by work order number.
        from_: Filter by start date (ISO format).
        to: Filter by end date (ISO format).
        modified_after: Filter by modification date (ISO format).
        status: Filter by order status.

    Returns:
        A list of ServiceOrdersToClientOrderResponseModel objects.
    """
    import datetime as dt

    kwargs: dict = {}
    if work_order_number is not None:
        kwargs["work_order_number"] = work_order_number
    if from_ is not None:
        kwargs["from_"] = dt.datetime.fromisoformat(from_)
    if to is not None:
        kwargs["to"] = dt.datetime.fromisoformat(to)
    if modified_after is not None:
        kwargs["modified_after"] = dt.datetime.fromisoformat(modified_after)
    if status is not None:
        kwargs["status"] = status

    try:
        response = get_work_orders.sync(client=make_qualer_client(), **kwargs)
    except httpx.ConnectError:
        check_connectivity()
        cp.red("Unable to connect to Qualer. Aborting...")
        raise SystemExit

    if response is None:
        cp.red(ERROR_FLAG)
        cp.red("Failed to fetch service orders (received None).")
        return []

    cp.white(f"{len(response)} service orders found.")
    return response


def getServiceOrderId(workOrderNumber: str) -> Optional[int]:
    """Get the service order ID for a work order number.

    Args:
        workOrderNumber: Work order number.

    Returns:
        The service order ID (int), or None if not found.
    """
    cp.white("Fetching service order id for work order: " + workOrderNumber + "...")
    try:
        response = get_service_orders(work_order_number=workOrderNumber)
        if len(response) == 0:
            cp.red(ERROR_FLAG)
            cp.red(f"No service order found for work order: {workOrderNumber}")
            return None
        return response[0].service_order_id
    except Exception as e:
        handle_exception(e)
        return None


def upload(
    filepath: str,
    serviceOrderId: int,
    qualertype: str,
    private: bool = False,
) -> tuple[bool, str]:
    """Upload a file to a Qualer service order.

    Args:
        filepath: Path to the file to upload.
        serviceOrderId: The service order ID.
        qualertype: The Qualer document/report type.
        private: If ``True``, set ``model_is_private`` on the API call so that
            Qualer marks the uploaded document as private. This is used for
            AI-reviewed/annotated documents which shouldn't be visible to end
            users.

    Returns:
        A tuple of (success: bool, filepath: str).
    """
    cp.white(f"Attempting upload for SO# {serviceOrderId}: '{path.basename(filepath)}'")

    if not path.exists(filepath):
        cp.red(ERROR_FLAG)
        cp.red(f"{filepath} does not exist")
        return False, filepath
    attempts = 0

    while attempts < 5:
        if attempts > 0:
            renamed = False
            candidate = filepath
            for _ in range(50):
                new_filename = pdf.increment_filename(candidate)
                if pdf.try_rename(filepath, new_filename):
                    filepath = new_filename
                    renamed = True
                    break
                candidate = new_filename
            if not renamed:
                cp.red(f"Failed to rename {filepath} after multiple increment attempts")
                return False, filepath
        with open(filepath, "rb") as file:
            upload_file = File(
                payload=file,
                file_name=path.basename(filepath),
                mime_type="application/pdf",
            )

            if attempts > 0:
                cp.white("Retrying upload...")
            try:
                r = upload_documents_post_2.sync_detailed(
                    service_order_id=serviceOrderId,
                    client=make_qualer_client(),
                    files=[upload_file],
                    model_report_type=qualertype,
                    model_is_private=private,
                )

            except httpx.TimeoutException as e:
                cp.yellow(str(e))
                attempts += 1
                continue

            if r.status_code == 200:
                cp.green("Upload successful!")
                return True, filepath

            error_message = ""
            try:
                response_data = json.loads(r.content)
                error_message = response_data.get("Message", "")
            except Exception as e:
                handle_exception(e)

            if (
                r.status_code == 400
                and error_message
                == "This document version is locked and cannot be overwritten."
            ):
                cp.yellow(error_message)
                attempts += 1
                # No return, so that we can try again after the file is renamed.
            else:  # if r.status_code != 200
                cp.red(ERROR_FLAG)
                cp.red(f"STATUS CODE: {r.status_code}")
                cp.red(f"RESPONSE: {r.content.decode()}")
                return False, filepath

    # All retry attempts exhausted
    return False, filepath


def get_service_order_document_list(ServiceOrderId: int) -> Optional[List[str]]:
    """Get a list of document filenames for a service order.

    Args:
        ServiceOrderId: The service order ID.

    Returns:
        A list of filenames, or None on error.
    """
    if not ServiceOrderId:
        cp.red(ERROR_FLAG)
        cp.red("ServiceOrderId not provided.")
        raise SystemExit

    cp.white(
        f"Fetching document list for service order: https://jgiquality.qualer.com/ServiceOrder/Info/{ServiceOrderId}..."
    )

    try:
        response = get_documents_list.sync(
            service_order_id=ServiceOrderId, client=make_qualer_client()
        )
    except Exception as e:
        handle_exception(e)
        return None

    if response is None:
        cp.red(ERROR_FLAG)
        cp.red(f"Failed to fetch document list for SO {ServiceOrderId}")
        return None

    file_names = [doc.file_name for doc in response]
    cp.white(
        f"Found {len(file_names)} documents at https://jgiquality.qualer.com/ServiceOrder/Info/{ServiceOrderId}"
    )
    return file_names


def get_work_items(service_order_id: int) -> list:
    """Fetch work items for a service order from the Qualer API.

    Args:
        service_order_id: The service order ID.

    Returns:
        A list of work item objects, or an empty list on error.
    """
    cp.white(f"Fetching work items for service order: {service_order_id}...")
    try:
        response = _sdk_get_work_items.sync(
            service_order_id, client=make_qualer_client()
        )
    except Exception as e:
        handle_exception(e)
        return []

    if response is None:
        cp.yellow(f"No work items found for SO {service_order_id}")
        return []

    cp.white(f"Found {len(response)} work items for SO {service_order_id}")
    return response
