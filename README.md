# PDF Processor and Uploader

This project provides a complete solution for processing and uploading PDF files to the Qualer API. It includes functionality for OCR, PDF rotation, file watching, and automated uploads, with robust error handling and support for incremental updates.

---

## Table of Contents

- [PDF Processor and Uploader](#pdf-processor-and-uploader)
  - [Table of Contents](#table-of-contents)
  - [Features](#features)
  - [Setup](#setup)
    - [Requirements](#requirements)
    - [Installation](#installation)
      - [Setting up the virtual environment](#setting-up-the-virtual-environment)
    - [Configuration](#configuration)
  - [Usage](#usage)
    - [Starting the program:](#starting-the-program)
      - [Run with Python:](#run-with-python)
      - [Run executable:](#run-executable)
    - [Operating instructions](#operating-instructions)
    - [Workflow Overview](#workflow-overview)
  - [Development](#development)
  - [License](#license)

---

## Features

- **PDF Manipulation**:

  - Backup OCR text extraction, in case there's no OCR from the
  - Detect PDF orientation; ensure each PDF is upright.
  - Split multi-page PDFs into pages for specific work orders (Going from the first to the last page, each time a detected workorder number is different than the previous, the page it's on will become the first page of the next document.)

- **File Automation**:

  - Automatically watch directories for new PDFs.
  - Identify document type, based on source, contents, or filename.
  - Archive or delete processed files based on settings.
  - Handle file renaming to avoid conflicts.

- **Integration**:

  - Upload PDFs to the Qualer API with detailed logging.
  - Retry and resolve naming conflicts during uploads.

---

## Setup

### Requirements

Ensure you have the following installed:

- Python 3.8+
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract)
- The following Python packages (install with `pip`):
  ```
  PyPDF2
  pytesseract
  requests
  pypdfium2
  watchdog
  opencv-python
  PyMuPDF
  numpy
  pdf2image
  Pillow
  colorama
  ```
- System dependencies:
  - Linux: `poppler-utils`, `tesseract-ocr`
  - Windows: Ensure `Tesseract` is installed and accessible.

---

### Installation

1. Clone the repository.**

#### Setting up the virtual environment

1. Create a virtual environment:

   ```bash
   python -m venv myenv
   ```

2. Activate the virtual environment:

   - On Linux/Mac:
     ```bash
     source myenv/bin/activate
     ```
   - On Windows:
     ```bash
     myenv\Scripts\activate
     ```

3. Install dependencies from `requirements.txt`:

   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the root directory of the project to securely store sensitive credentials. Add the following content:
   ```
   QUALER_USER=your_qualer_username
   QUALER_PASS=your_qualer_password
   ```
   This user must at least have the API security role.
   ![alt text](image.png)

   Talk to Jeff or Johnny if you need these credentials.

5. Ensure `.env` is added to your `.gitignore` file to prevent it from being committed to the repository.

6. Verify the setup:

   ```bash
   python -m pip list
   ```

7. (Optional) Create a standalone executable using `pyinstaller`:

   ```bash
   ./myenv/Scripts/activate

   pyinstaller --onefile --clean --add-data "myenv/Lib/site-packages/pypdfium2_raw/pdfium.dll;pypdfium2_raw" --add-data "myenv/Lib/site-packages/pypdfium2_raw/version.json;pypdfium2_raw" --add-data "myenv/Lib/site-packages/pypdfium2/version.json;pypdfium2" --add-data "app/dict.json.gz;_internal" watcher.py
   ```

---

### Configuration

Sensitive API credentials are securely stored in a `.env` file. Update your `.env` file with the following variables:

- `QUALER_USER`: Your Qualer username.
- `QUALER_PASS`: Your Qualer password.

Other settings are configured in `config.py`:

- **API settings**:
  - `QUALER_ENDPOINT`: The Qualer API endpoint.
- **Directory settings**:
  - `INPUT_DIR`, `OUTPUT_DIR`, `REJECT_DIR`: Paths for handling input and processed PDFs.
- **Other settings**:
  - `LIVEAPI`: Set to `True` for production, `False` for testing with the staging API.
  - `DELETE_MODE`: Set to `True` to delete old files or `False` to archive them.

---

## Usage

Choose one:

### Starting the program:

#### Run with Python:

1. Activate the virtual environment:
   ```bash
   source myenv/bin/activate # Linux/Mac
   ```
   or
   ```bash
   myenv\Scripts\activate     # Windows
   ```
2. Start the directory watcher:
   ```bash
   python watcher.py
   ```

#### Run executable:

```bash
watcher.exe
```

### Operating instructions

The `pdf_uploader` script automates the processing and categorization of scanned PDF files based on their filenames, content, and designated scanner output paths. This helps streamline document management and upload processes.



### Workflow Overview



1. **Scanner Configuration**:

   - **General Documents**: Scanned by a dedicated scanner and saved to:

     ```

     /OneDrive - Johnson Gage and Inspection, Inc/Shared with Everyone/access/!!! Front Office Scanned Docs - HOLDING

     ```

   - **Order Certificates**: Scanned by another scanner and saved to:

     ```

     /OneDrive - Johnson Gage and Inspection, Inc/Shared with Everyone/access/!!! Scanned External Certs

     ```



2. **Document Categorization**:

   - Based on internal naming conventions and business logic, documents are categorized into:
     - **Purchase Orders (POs)**: Likely associated with customer orders.

     - **Service Orders (SOs)**: Possibly internal or external service-related documents.

     - **Shippers**: May pertain to shipment confirmations or delivery notes.



3. **File Processing Logic**:

   - The script scans the file path and content to determine the document type:

     - Files scanned from the **General Documents** folder are treated as miscellaneous files unless their filenames or content indicate otherwise.

     - Files scanned from the **Order Certificates** folder are more likely to be categorized as POs or related documents.

   - The filename is adjusted as needed to resolve conflicts or provide additional context.



4. **Error Handling and Upload**:

   - If a file cannot be uploaded due to naming conflicts, content mismatches, or system errors, the script logs the issue for review.

   - Successfully processed files are archived or moved based on their outcome.



5. **Automatic Reorganization**:

   - Processed files are moved to designated directories:
     - **Accepted Files**: Stored in an archive directory after successful uploads.

     - **Rejected Files**: Stored in a rejection directory for further investigation.

---

## Development

- **File structure**:

  - `app/`: Core modules (e.g., `pdf.py`, `api.py`, `color_print.py`).
  - `config.py`: Configuration settings.
  - `watcher.py`: Watches directories and triggers file processing.
  - `PurchaseOrders.py`: Handles PO number management.
  - `onefile.bash`: Script for creating a standalone executable.

- **Virtual environment role**:

  - The `/myenv/` directory ensures isolated package management.
  - When building executables, dependencies in `/myenv/` are bundled, such as `pypdfium2_raw`.

---

## License

This project is licensed under the MIT License. See `LICENSE` for details.

