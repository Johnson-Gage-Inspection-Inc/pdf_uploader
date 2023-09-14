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

- LOGIN_USER: The Qualer username that will be used to upload the PDF files.
- LOGIN_PASS: The Qualer password that will be used to upload the PDF files.
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

# Switches:
LIVEAPI = True              # Set to True to use live API, False to use staging API, 
DEBUG = False               # Set to False to upload files, True to skip uploads
DELETE_MODE = False         # Set to True to delete old processed PDFs, False to move them to their "Old PDFs" subdirectory

# Qualer API login credentials:
# NOTE: User must have the sufficient permissions in Qualer: https://jgiquality.qualer.com/Company/Employees
LOGIN_USER = "joohhnnny@yahoo.com"
LOGIN_PASS = "jgiapi5920"
QUALER_ENDPOINT = "https://jgiquality.qualer.com/api" # Do not change this
QUALER_STAGING_ENDPOINT = "https://jgiquality.staging.qualer.com/api" # Do not change this

# Tesseract OCR path:
tesseract_cmd_path = r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'

# Dictionary of directories to watch:
CONFIG = [
    {
        'INPUT_DIR': 'L:\\!!! Front Office Scanned Docs - HOLDING',
        'OUTPUT_DIR': 'L:\\!!! Front Office Scanned Docs - HOLDING\\Archives',
        'REJECT_DIR': 'L:\\!!! Front Office Scanned Docs - HOLDING\\No_Order_Found',
        'QUALER_DOCUMENT_TYPE': 'General'
    },
    {
        'INPUT_DIR': 'L:\\!!! Scanned External Certs',
        'OUTPUT_DIR': 'L:\\!!! Scanned External Certs\\Archives',
        'REJECT_DIR': 'L:\\!!! Scanned External Certs\\No_Order_Found',
        'QUALER_DOCUMENT_TYPE': 'ordercertificate'
    }
]

"""
Dependencies (Whole program):
- PyPDF2 (for PDF manipulation): https://pypi.org/project/PyPDF2/
- pytesseract (for OCR): https://pypi.org/project/pytesseract/
- requests (for API): https://pypi.org/project/requests/
- pypdfium2 (for PDF to image conversion): https://pypi.org/project/pypdfium2/ 
- watchdog (for file watching): https://pypi.org/project/watchdog/
- opencv-python (for image manipulation): https://pypi.org/project/opencv-python/
- PyMuPDF (for PDF to image conversion): https://pypi.org/project/PyMuPDF/
- numpy (for image manipulation): https://pypi.org/project/numpy/
- pdf2image (for PDF to image conversion): https://pypi.org/project/pdf2image/
- Pillow (for image manipulation): https://pypi.org/project/Pillow/
- colorama (for colored console output): https://pypi.org/project/colorama/

pip3 install PyPDF2 pytesseract requests pypdfium2 watchdog opencv-python PyMuPDF numpy pdf2image Pillow colorama
"""
