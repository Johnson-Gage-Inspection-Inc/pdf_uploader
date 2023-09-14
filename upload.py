"""
upload.py

!/bin/python3

dependencies (linux):
sudo apt install poppler-utils
sudo apt install tesseract-ocr (or, install windows tesseract)

windows/linux
pip3 install PyPDF2 pytesseract requests pypdfium2
"""

import datetime as dt
import os
import traceback
import app.color_print as cp

from PurchaseOrders import update_PO_numbers, file_path, extract_po
import app.api as api
import app.pdf as pdf
from config import *

if not LIVEAPI:
    QUALER_ENDPOINT = QUALER_STAGING_ENDPOINT
    cp.yellow("Using staging API")

token = api.login(QUALER_ENDPOINT, LOGIN_USER, LOGIN_PASS)

total = 0

# Rename File
def rename_file(filepath,doc_list):
    try:
        print("File already exists in Qualer. Renaming file...")
        file_name = os.path.basename(filepath)
        attempts = 10
        did_rename = False
        new_filepath = filepath
        while not did_rename and attempts > 0:                                         # try to rename the file up to 10 times
            new_filepath = pdf.increment_filename(new_filepath)                         # Increment the filename
            new_filename = os.path.basename(new_filepath)
            if new_filename not in doc_list:                                            # If the file does not exist in Qualer, upload it
                did_rename = pdf.try_rename(filepath, new_filepath)                     # Try to rename the file
            attempts -= 1
        cp.green("'"+file_name+"' renamed to: '"+new_filename+"'")
        return new_filepath
    except FileNotFoundError:
        raise
    except Exception as e:
        cp.red("Error in rename_file(): "+str(e)+"\nFile: "+filepath)
        traceback.print_exc()
        return filepath

# Upload file to Qualer endpoint, and resolve name conflicts
def upload_with_rename(filepath,serviceOrderId,QUALER_DOCUMENT_TYPE):
    file_name = os.path.basename(filepath) # Get file name
    doc_list = api.get_service_order_document_list(QUALER_ENDPOINT,token,serviceOrderId) # get list of documents for the service order
    new_filepath = rename_file(filepath, doc_list) if file_name in doc_list else filepath # if the file already exists in Qualer, rename it
    uploadResult, new_filepath = api.upload(QUALER_ENDPOINT, token, new_filepath, serviceOrderId, QUALER_DOCUMENT_TYPE) if not DEBUG else print("debug mode, no uploads")
    return uploadResult, new_filepath

# Get service order ID and upload file to Qualer endpoint
def fetch_SO_and_upload(workorder,filepath,QUALER_DOCUMENT_TYPE):
    try:
        if not os.path.isfile(filepath): # See if filepath is valid
            return False, filepath
        serviceOrderId = api.getServiceOrderId(QUALER_ENDPOINT, token, workorder)
        return upload_with_rename(filepath,serviceOrderId,QUALER_DOCUMENT_TYPE) # return uploadResult, new_filepath
    except FileNotFoundError as e:
        cp.red("Error: "+filepath+" not found.")
        return False, filepath
    except Exception as e:
        cp.red("Error in fetch_SO_and_upload(): "+str(e)+"\nFile: "+filepath)
        traceback.print_exc()
        return False, filepath
    
# Get service order ID and upload file to Qualer endpoint
def upload_by_po(filepath, po, dict, QUALER_DOCUMENT_TYPE):
    if po not in dict:
        cp.yellow("PO#"+po+" not found in Qualer.")
        return [], [], filepath
    serviceOrderIds = dict[po]
    cp.green("Found " + str(len(serviceOrderIds)) + " service orders for PO " + po + ": " + str(serviceOrderIds))
    successSOs = []
    failedSOs = []
    for serviceOrderId in serviceOrderIds:
        try:
            if not os.path.isfile(filepath):
                return [], serviceOrderIds, filepath
            uploadResult, filepath = upload_with_rename(filepath,serviceOrderId,QUALER_DOCUMENT_TYPE) # return uploadResult, new_filepath
            if uploadResult:
                successSOs.append(serviceOrderId)
            else:
                failedSOs.append(serviceOrderId)
        except FileNotFoundError as e:
            cp.red("Error: "+filepath+" not found.")
            return [], serviceOrderIds, filepath
        except Exception as e:
            cp.red("Error in fetch_SO_and_upload(): "+str(e)+"\nFile: "+filepath)
            traceback.print_exc()
            return [], serviceOrderIds, filepath
    return successSOs, failedSOs, filepath

def reorient_pdf_for_workorders(filepath,REJECT_DIR):
    file_name = os.path.basename(filepath)
    try:
        print("Checking orientation of PDF file... " + file_name)
        orientation = pdf.get_pdf_orientation(filepath)  # get orientation of PDF file
        print("Orientation: " + str(orientation) + " | " + file_name)
        if orientation in [90, 180, 270]:
            cp.yellow("Orientation: " + str(orientation) + " | " + file_name)
            print("Rotating PDF file... " + file_name)
            did_rotate = pdf.rotate_pdf(filepath, orientation)  # rotate PDF file
            if did_rotate:
                cp.green(file_name + " file rotated successfully.")
            workorders = pdf.workorders(filepath)  # parse work order numbers from PDF file name/body
            if workorders:
                return workorders
            else:  # If there are still no work orders, skip the file
                cp.yellow("no work order found in " + file_name + ", file skipped")
                pdf.move_file(filepath, REJECT_DIR)  # move file to reject directory
                return False  # return False to main loop
        elif orientation == 0:
            print("File appears to be right-side-up. Moving file to reject directory...")
            pdf.move_file(filepath, REJECT_DIR)  # move file to reject directory
        else:
            cp.yellow("Reorientation of " + file_name + " failed. Skipping file...")
            print("Moving file to reject directory...")
            pdf.move_file(filepath, REJECT_DIR)  # move file to reject directory
            return False
    except FileNotFoundError as e:
        cp.red("Error:" + filepath + " not found.")
        return False
    except Exception as e:
        cp.red("Error: " + str(e) + "\nFile: " + file_name)
        return False


# Main function
def process_file(filepath,qualer_parameters):
    cp.blue("Processing file: " + filepath)
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
        po = extract_po(filename)
        po_dict = update_PO_numbers(file_path, token)
        print("PO found in file name: " + po)
        successSOs, failedSOs, new_filepath = upload_by_po(filepath, po, po_dict, QUALER_DOCUMENT_TYPE)
        if successSOs:
            cp.green(filename + " uploaded successfully to SOs: " + str(successSOs))
            uploadResult = True
        if failedSOs:
            cp.red(filename + " failed to upload to SOs: " + str(failedSOs))

    if not uploadResult:
        # Check for work orders in file body or file name
        workorders = pdf.workorders(filepath) # parse work order numbers from PDF file name/body

        # if no work orders found, check the orientation of the PDF file.
        if not workorders:
            workorders = reorient_pdf_for_workorders(filepath,REJECT_DIR)
            if not workorders:
                return False

        # if work orders found in filename, upload file to Qualer endpoint(s)
        if type(workorders) == list:                                                    # A list of work orders was found in the file name
            cp.green("Work order(s) found in file name: "+ str(workorders))             # Print the work order numbers
            for workorder in workorders:                                                # loop through work orders list and upload
                uploadResult, new_filepath = fetch_SO_and_upload(workorder,filepath,QUALER_DOCUMENT_TYPE) # upload file

        elif len(workorders) == 1:                                                      # One work order was found in the file body (dict object of length 1)
            workorder = list(workorders.keys())[0]                                      # Get the work order number           
            cp.green("One (1) work order found within file: "+ str(workorder))          # Print the work order number
            uploadResult, new_filepath = fetch_SO_and_upload(workorder,filepath,QUALER_DOCUMENT_TYPE) # Upload the file

        else:                                                                           # For multiple work orders,
            cp.green("Multiple work orders found within file: "+ str(workorders))       # Print the work order numbers
            for workorder, pg_nums in workorders.items():                               # loop through the workorders dict object,
                now = dt.datetime.now().strftime("%Y%m%dT%H%M%S")                       # get the current date and time,
                child_pdf_path = f'{INPUT_DIR}\scanned_doc_{workorder}_{now}.pdf'       # create a new file path for the extracted pages,
                pdf.create_child_pdf(filepath, pg_nums, child_pdf_path)                 # extract relevant pages from PDF, and
                uploadResult, new_child_pdf_path = fetch_SO_and_upload(workorder,child_pdf_path,QUALER_DOCUMENT_TYPE) # upload extracted pages
                child_pdf_path = new_child_pdf_path if new_child_pdf_path else child_pdf_path   # if the file was renamed, update the filepath
                try:
                    # Remove child files after upload
                    os.remove(child_pdf_path) if uploadResult else cp.red("Failed to upload and remove "+child_pdf_path)
                except Exception as e:
                    cp.red(e)

    # If the upload failed, move the file to the reject directory
    if not uploadResult and os.path.isfile(filepath):
        cp.red("Failed to upload "+filepath+". Moving to reject directory...")
        pdf.move_file(filepath, REJECT_DIR)
        return False

    # If the file was renamed, update the filepath
    if new_filepath: 
        filepath = new_filepath

    # Remove file if there were no failures
    # (if there were any failures, file will remain)
    try:
        if filepath and (OUTPUT_DIR == None or OUTPUT_DIR == ''):
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
                while file_was_moved == False:
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
        cp.red(e)
        cp.red("Failed to remove file: "+filepath)
