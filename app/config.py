"""
config.py

This file is used to configure the PDF uploader. It contains the following variables:
- LIVEAPI:
    - Set to True to use live API (Used for production), False to use staging API (Used for testing)
- DEBUG:
    - Set to False to upload files, True to skip uploads (Used for testing)
- DELETE_MODE:
  - Set to True to delete PDF files that were processed before the current date.
  - Set to False to move them to their respective "Old PDFs" subdirectory.

- LOGIN_USER: This is now stored in .env instead of here!
- LOGIN_PASS: This is now stored in .env instead of here!
- QUALER_ENDPOINT: The Qualer API endpoint that will be used to upload the PDF files.
- QUALER_STAGING_ENDPOINT: The Qualer staging API endpoint which is used for testing.

- CONFIG: A list of dictionaries that contain the following keys:
  - INPUT_DIR: The directory that the watcher will watch for new PDF files.
  - OUTPUT_DIR: The directory that the processed PDF files will be archived if they
    are successfully uploaded. *Leave this blank to delete the files instead.*
  - REJECT_DIR: The directory that the processed PDF files will be moved to if they
    are not successfully uploaded.
  - QUALER_DOCUMENT_TYPE: The Qualer document type that will be used to upload the
    PDF files from the INPUT_DIR. The following document types are available:
    - general, assetsummary, assetlabel, assetdetail, assetcertificate, ordersummary,
    - orderinvoice, orderestimate, dashboard, orderdetail, ordercertificate
"""

from os import path

MAX_RUNTIME = None  # Set this to the maximum number of seconds the script should run before stopping. Set to None to run indefinitely.

# Switches:
LIVEAPI = True  # Set to True to use live API, False to use staging API,
DEBUG = False  # Set to False to upload files, True to skip uploads
DELETE_MODE = False  # Set to True to delete old processed PDFs, False to move them to their "Old PDFs" subdirectory

# Tesseract OCR path:
tesseract_cmd_path = r"C:/Program Files/Tesseract-OCR/tesseract.exe"  # Path to the Tesseract OCR executable

# Get the user's home directory
user_folder = path.expanduser("~")  # e.g. 'C:\Users\JohnDoe'
SHAREPOINT_PATH = (
    user_folder
    + "/Johnson Gage and Inspection, Inc/Johnson Gage and Inspection, Inc. - Documents/Sysop's OneDrive/Shared with Everyone/access/"
)
LOG_FILE = SHAREPOINT_PATH + r"Logs/pdfUploader.log"

# Dictionary of directories to watch:
CONFIG = [
    {
        "INPUT_DIR": SHAREPOINT_PATH + r"/!!! Front Office Scanned Docs - HOLDING",
        "OUTPUT_DIR": SHAREPOINT_PATH
        + r"/!!! Front Office Scanned Docs - HOLDING/Archives",
        "REJECT_DIR": SHAREPOINT_PATH
        + r"/!!! Front Office Scanned Docs - HOLDING/No_Order_Found",
        "QUALER_DOCUMENT_TYPE": "General",
    },
    {
        "INPUT_DIR": SHAREPOINT_PATH + r"/!!! Scanned External Certs",
        "OUTPUT_DIR": SHAREPOINT_PATH + r"/!!! Scanned External Certs/Archives",
        "REJECT_DIR": SHAREPOINT_PATH + r"/!!! Scanned External Certs/No_Order_Found",
        "QUALER_DOCUMENT_TYPE": "ordercertificate",
    },
]

QUALER_ENDPOINT = "https://jgiquality.qualer.com/api"  # Do not change this
QUALER_STAGING_ENDPOINT = (
    "https://jgiquality.staging.qualer.com/api"  # Do not change this
)
