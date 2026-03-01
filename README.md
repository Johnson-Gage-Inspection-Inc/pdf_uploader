<p align="center">
    <!-- <img src="https://raw.githubusercontent.com/PKief/vscode-material-icon-theme/ec559a9f6bfd399b82bb44393651661b08aaf7ba/icons/folder-markdown-open.svg" align="center" width="30%"> -->
</p>
<p align="center"><h1 align="center">PDF Processor and Uploader</h1></p>
<p align="center">
  <em>Streamline PDF uploads for seamless Qualer connections.</em>
</p>
<p align="center">
  <img src="https://img.shields.io/github/last-commit/Johnson-Gage-Inspection-Inc/pdf_uploader?style=default&logo=git&logoColor=white&color=0080ff" alt="last-commit">
  <img src="https://img.shields.io/github/languages/top/Johnson-Gage-Inspection-Inc/pdf_uploader?style=default&color=0080ff" alt="repo-top-language">
  <img src="https://img.shields.io/github/languages/count/Johnson-Gage-Inspection-Inc/pdf_uploader?style=default&color=0080ff" alt="repo-language-count">
  <img src="https://img.shields.io/github/v/release/Johnson-Gage-Inspection-Inc/pdf_uploader?style=default&logo=github&logoColor=white&color=0080ff" alt="latest-release">
</p>
<p align="center"><!-- default option, no dependency badges. -->
</p>
<p align="center">
  <!-- default option, no dependency badges. -->
</p>
<br>

##  Table of Contents

<!-- TOC -->

- [Table of Contents](#table-of-contents)
- [Overview](#overview)
- [Features](#features)
- [Project Structure](#project-structure)
  - [Project Index](#project-index)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Configuration](#configuration)
- [Usage](#usage)
  - [Starting the program](#starting-the-program)
  - [Operation Overview](#operation-overview)
- [Contributing](#contributing)
- [Acknowledgments](#acknowledgments)

<!-- /TOC -->

## Overview

The pdfuploader project is designed to simplify the process of uploading scanned documents to Qualer. It features a robust architecture with key components such as file processing tools, connectivity checks, and archive management. The project includes a **PyQt6-based GUI** with a live dashboard, log viewer, and system tray support, as well as a headless CLI mode. It handles various scenarios including successful uploads, failed uploads, file renaming, PO validation, and multi-instance file claiming, while ensuring compatibility across different environments and platforms.

---

##  Features

| Feature         | Summary       |
| :--- | :---:           |
| **GUI Dashboard** | *   PyQt6-based desktop application with a live dashboard, log viewer, and system tray icon.  *   Dashboard shows summary counters (total, uploaded, failed, no order, processing).  *   File table with clickable work order hyperlinks to Qualer.  *   Detail dialog shows PO validation breakdown for PO files and basic upload info for other documents.  *   Minimize-to-tray support — keeps running in the background. |
| **PO Validation** | *   Extracts line items from purchase order PDFs.  *   Compares prices against Qualer work items.  *   Generates annotated PDFs highlighting mismatches and missing items.  *   Uploads annotated results as private documents. |
| **PDF Correction** |  *   Backup OCR if not provided by the scanner.  *   Ensure PDFs are upright by detecting and correcting orientation.  *   Split multi-page PDFs into separate files when a new work order number is detected.|
| **Automatic Triggers** |  *   Automatically watch directories for new PDFs.  *   Identify document type based on source, contents, or filename.  *   Archive or delete processed files based on settings.  *   Handle file renaming to avoid conflicts.|
| **Multi-Instance Safety** | *   Atomic claim-by-move prevents multiple machines from processing the same file.  *   PermissionError retry handles OneDrive/antivirus file locks.  *   Observer thread is guarded against crashes to keep watching after errors. |
| **Integration** |  *   Upload PDFs to the Qualer API with detailed logging.  *   Retry and resolve naming conflicts during uploads.  *   Work order number lookup with API fallback and caching. |
| ⚙️ **Architecture** |  *   Modular design with separate modules for API gateway, file processing, GUI, PO validation, and configuration.  *   YAML-based configuration (`config.yaml`) with backward-compatible `config.py` facade.  *   Event bus for decoupled GUI updates from watcher threads.  *   Supports live or staging API usage, file uploads or skips, and deletion or archiving of processed files. |
| 📊 **Data Processing** |  *   Employs data processing techniques to extract relevant pages from PDFs, including `extract`, `workorders`, and `create_child_pdf` functions.  *   Supports file rename errors using the `try_rename` function with retry logic.  *   Purchase order dictionary with SO→WO mapping, persisted as compressed JSON.  *   API fallback for work order numbers on cache miss. |
| 🌐 **Connectivity** |  *   Verifies internet availability by pinging Google's address.  *   Checks accessibility of SharePoint and Qualer servers.  *   Verifies the existence of the SharePoint directory.  *   Provides real-time feedback on system connections for informed decision-making. |
| 💻 **Development Tools** |  *   Python 3.14 with PyQt6 for the GUI.  *   PyInstaller for packaging as a single-file windowed `.exe`.  *   `colorama` for colorized console logging.  *   PyMuPDF (fitz), pypdf, Tesseract OCR for PDF processing. |
| 📁 **Configuration** |  *   YAML-based configuration file (`config.yaml`) for all settings.  *   Configures API endpoints, directory paths, upload settings, and PO validation per folder.  *   Backward-compatible `config.py` facade via PEP 562 `__getattr__`.  *   Supports `{sharepoint_path}` variable interpolation in paths. |

---

##  Project Structure

```sh
└── pdf_uploader/
    ├── README.md
    ├── config.yaml           # Main configuration file
    ├── app/
    │   ├── api.py            # Qualer API gateway
    │   ├── archive.py        # File archiving
    │   ├── color_print.py    # Colorized logging
    │   ├── config.py         # Config facade (reads config.yaml)
    │   ├── config_manager.py # YAML config loader
    │   ├── connectivity.py   # Network checks
    │   ├── event_bus.py      # PyQt signal bus for GUI
    │   ├── orientation.py    # PDF orientation detection
    │   ├── pdf.py            # PDF processing utilities
    │   ├── PurchaseOrders.py # PO dictionary & SO→WO mapping
    │   ├── qualer_client.py  # SDK client factory
    │   ├── version.py        # Build version tag
    │   ├── gui/
    │   │   ├── main_window.py      # Main application window
    │   │   ├── dashboard_widget.py # Dashboard tab
    │   │   ├── detail_dialog.py    # Validation detail dialog
    │   │   ├── log_widget.py       # Log viewer tab
    │   │   ├── config_dialog.py    # Settings dialog
    │   │   ├── tray_icon.py        # System tray icon
    │   │   └── resources.py        # Icons & resources
    │   └── po_validator/
    │       ├── extractor.py  # PO line item extraction
    │       ├── annotator.py  # PDF annotation with results
    │       ├── models.py     # Pydantic data models
    │       └── reporter.py   # Validation reporting
    ├── hooks/
    │   └── hook-qualer_sdk.py # PyInstaller collection hook
    ├── stubs/                 # Type stubs for untyped deps
    ├── tests/
    ├── upload.py              # Main file processing logic
    ├── watcher.py             # Directory watcher & entry point
    ├── requirements.txt
    ├── PDF_Uploader.spec      # PyInstaller build spec
    └── .env                   # You must create this
```


### Project Index
<details open>
  <summary><b><code>pdf_uploader/</code></b></summary>
  <details>
    <summary><b>__root__</b></summary>
    <blockquote>
      <table>
      <tr>
        <td><b><a href='https://github.com/Johnson-Gage-Inspection-Inc/pdf_uploader/blob/master/upload.py'>upload.py</a></b></td>
        <td>- The main file processing script. Uploads scanned documents to Qualer endpoint(s) based on the presence of work orders or PO numbers within the file name or body.<br>- Implements claim-by-move for multi-instance safety, PO validation with annotated uploads, and retry logic for file locking.</td>
      </tr>
      <tr>
        <td><b><a href='https://github.com/Johnson-Gage-Inspection-Inc/pdf_uploader/blob/master/watcher.py'>watcher.py</a></b></td>
        <td>- Entry point for both GUI and CLI modes.<br>- Monitors directories for new PDF files using the watchdog library, waits for file stability before processing, and checks connectivity periodically.<br>- In GUI mode, launches a PyQt6 dashboard with system tray support.</td>
      </tr>
      <tr>
        <td><b><a href='https://github.com/Johnson-Gage-Inspection-Inc/pdf_uploader/blob/master/config.yaml'>config.yaml</a></b></td>
        <td>- Main configuration file. Defines API endpoints, watched folders, document types, PO validation settings, and path templates with <code>{sharepoint_path}</code> interpolation.</td>
      </tr>
      <tr>
        <td><b><a href='https://github.com/Johnson-Gage-Inspection-Inc/pdf_uploader/blob/master/requirements.txt'>requirements.txt</a></b></td>
        <td>- Lists the dependencies required for the project, including PyQt6, qualer-sdk, PyMuPDF, watchdog, and others.</td>
      </tr>
      </table>
    </blockquote>
  </details>
  <details>
    <summary><b>app</b></summary>
    <blockquote>
      <table>
      <tr>
        <td><b><a href='https://github.com/Johnson-Gage-Inspection-Inc/pdf_uploader/blob/master/app/api.py'>api.py</a></b></td>
        <td>- Central API gateway for Qualer integration.<br>- Provides functions for fetching service orders (bulk and single), uploading files (with private flag support), and retrieving document lists.</td>
      </tr>
      <tr>
        <td><b><a href='https://github.com/Johnson-Gage-Inspection-Inc/pdf_uploader/blob/master/app/PurchaseOrders.py'>PurchaseOrders.py</a></b></td>
        <td>- Manages a dictionary of purchase orders and their corresponding service order IDs.<br>- Caches SO→WO (work order number) mappings with API fallback on cache miss.<br>- Persists data as compressed JSON with backward compatibility for old cache formats.</td>
      </tr>
      <tr>
        <td><b><a href='https://github.com/Johnson-Gage-Inspection-Inc/pdf_uploader/blob/master/app/config_manager.py'>config_manager.py</a></b></td>
        <td>- YAML-based configuration loader using Pydantic models.<br>- Resolves <code>{sharepoint_path}</code> placeholders and <code>~</code> in paths.</td>
      </tr>
      <tr>
        <td><b><a href='https://github.com/Johnson-Gage-Inspection-Inc/pdf_uploader/blob/master/app/event_bus.py'>event_bus.py</a></b></td>
        <td>- PyQt signal bus for decoupled communication between watcher threads and the GUI.<br>- Emits signals for file processing lifecycle, watcher status, connectivity changes, and log messages.</td>
      </tr>
      <tr>
        <td><b><a href='https://github.com/Johnson-Gage-Inspection-Inc/pdf_uploader/blob/master/app/connectivity.py'>connectivity.py</a></b></td>
        <td>- Ensures internet availability by pinging Google's address.<br>- Checks accessibility of SharePoint and Qualer servers.<br>- Uses <code>CREATE_NO_WINDOW</code> to prevent console popups from windowed exe.</td>
      </tr>
      <tr>
        <td><b><a href='https://github.com/Johnson-Gage-Inspection-Inc/pdf_uploader/blob/master/app/pdf.py'>pdf.py</a></b></td>
        <td>- PDF processing module with functions for text extraction, orientation correction, work order detection, file splitting, and renaming with retry logic for transient file locks.</td>
      </tr>
      <tr>
        <td><b><a href='https://github.com/Johnson-Gage-Inspection-Inc/pdf_uploader/blob/master/app/archive.py'>archive.py</a></b></td>
        <td>- Archives files older than today by compressing them into a zip folder.</td>
      </tr>
      <tr>
        <td><b><a href='https://github.com/Johnson-Gage-Inspection-Inc/pdf_uploader/blob/master/app/color_print.py'>color_print.py</a></b></td>
        <td>- Colorized logging with optional GUI handler that forwards messages to the event bus for display in the log viewer tab.</td>
      </tr>
      <tr>
        <td><b><a href='https://github.com/Johnson-Gage-Inspection-Inc/pdf_uploader/blob/master/app/config.py'>config.py</a></b></td>
        <td>- Backward-compatible facade over <code>config_manager</code>.<br>- All existing <code>from app.config import X</code> imports continue to work via PEP 562 <code>__getattr__</code>.</td>
      </tr>
      </table>
    </blockquote>
  </details>
  <details>
    <summary><b>app/gui</b></summary>
    <blockquote>
      <table>
      <tr>
        <td><b><a href='https://github.com/Johnson-Gage-Inspection-Inc/pdf_uploader/blob/master/app/gui/main_window.py'>main_window.py</a></b></td>
        <td>- Main application window with tabbed interface (Dashboard + Log) and system tray integration.</td>
      </tr>
      <tr>
        <td><b><a href='https://github.com/Johnson-Gage-Inspection-Inc/pdf_uploader/blob/master/app/gui/dashboard_widget.py'>dashboard_widget.py</a></b></td>
        <td>- Dashboard tab showing summary counters, processed-file table with clickable WO# hyperlinks, validation status, and watched folder indicators.</td>
      </tr>
      <tr>
        <td><b><a href='https://github.com/Johnson-Gage-Inspection-Inc/pdf_uploader/blob/master/app/gui/detail_dialog.py'>detail_dialog.py</a></b></td>
        <td>- Modal dialog for viewing file details. Shows PO validation breakdown (mismatches, missing items, extraction info) for PO files, and basic upload info for non-PO files.</td>
      </tr>
      <tr>
        <td><b><a href='https://github.com/Johnson-Gage-Inspection-Inc/pdf_uploader/blob/master/app/gui/log_widget.py'>log_widget.py</a></b></td>
        <td>- Log viewer tab displaying real-time color-coded log messages from all watcher threads.</td>
      </tr>
      <tr>
        <td><b><a href='https://github.com/Johnson-Gage-Inspection-Inc/pdf_uploader/blob/master/app/gui/tray_icon.py'>tray_icon.py</a></b></td>
        <td>- System tray icon with show/hide and quit actions. Keeps the application running when the window is closed.</td>
      </tr>
      <tr>
        <td><b><a href='https://github.com/Johnson-Gage-Inspection-Inc/pdf_uploader/blob/master/app/gui/config_dialog.py'>config_dialog.py</a></b></td>
        <td>- Settings dialog for editing configuration at runtime.</td>
      </tr>
      </table>
    </blockquote>
  </details>
  <details>
    <summary><b>app/po_validator</b></summary>
    <blockquote>
      <table>
      <tr>
        <td><b><a href='https://github.com/Johnson-Gage-Inspection-Inc/pdf_uploader/blob/master/app/po_validator/models.py'>models.py</a></b></td>
        <td>- Pydantic data models for PO extraction and validation results, including line items, price mismatches, missing work items, and annotations.</td>
      </tr>
      <tr>
        <td><b><a href='https://github.com/Johnson-Gage-Inspection-Inc/pdf_uploader/blob/master/app/po_validator/extractor.py'>extractor.py</a></b></td>
        <td>- Extracts structured line item data from purchase order PDFs using table parsing and text extraction.</td>
      </tr>
      <tr>
        <td><b><a href='https://github.com/Johnson-Gage-Inspection-Inc/pdf_uploader/blob/master/app/po_validator/annotator.py'>annotator.py</a></b></td>
        <td>- Annotates PO PDFs with validation results — draws colored borders, stamps, and summary pages.</td>
      </tr>
      <tr>
        <td><b><a href='https://github.com/Johnson-Gage-Inspection-Inc/pdf_uploader/blob/master/app/po_validator/reporter.py'>reporter.py</a></b></td>
        <td>- Compares extracted PO line items against Qualer work items and produces a ValidationResult.</td>
      </tr>
      </table>
    </blockquote>
  </details>
</details>

---
##  Getting Started

If you're just here to download and use the program, you may simply download the [latest release](https://github.com/Johnson-Gage-Inspection-Inc/pdf_uploader/releases/latest).

The following are instructions for building the program from source.

### Prerequisites

Before getting started with pdf_uploader, ensure your runtime environment meets the following requirements:

- **Programming Language:** Python 3.14+
- **Package Manager:** Pip
- **Tesseract OCR:** [Install Tesseract](https://github.com/tesseract-ocr/tesseract) and configure the path in `config.yaml`


###  Installation

Install pdf_uploader using one of the following methods:

**Build from source:**

1. Clone the pdf_uploader repository:
  ```sh
  git clone https://github.com/Johnson-Gage-Inspection-Inc/pdf_uploader
  ```

2. Navigate to the project directory:
  ```sh
  cd pdf_uploader
  ```
3. Prepare a virtual environment

    1. Create a virtual environment:

        ```sh
        python -m venv .venv
        ```

    2. Activate the virtual environment:

        ```sh
        .venv\Scripts\activate  # Windows
        ```

        ```bash
        source .venv/bin/activate  # Linux/Mac
        ```

    3. Install the project dependencies:

        ```sh
        pip install -r requirements.txt
        ```

    4. (Optional) Verify the setup:

        ```sh
        python -m pytest tests/
        ```

4. Configure your project
  See [configuration](#configuration).

5. (Optional) Compile a standalone executable using `pyinstaller`:
  With the virtual environment still active, you can compile a binary using `pyinstaller`

  ```
  pyinstaller PDF_Uploader.spec --noconfirm
  ```
  Creating a standalone executable ensures the program can run without requiring Python, dependencies, or credentials on the target system.  Alternatively, you can simply download the latest release from [the releases page](https://github.com/Johnson-Gage-Inspection-Inc/pdf_uploader/releases/latest), precompiled.

---

### Configuration

1. Create a `.env` file in the root directory of the project to securely store sensitive credentials. Add the following content:
    ```
    QUALER_EMAIL=your_email
    QUALER_PASSWORD=your_password
    ```

    This user must at least have the API security role in [Employee Settings](https://jgiquality.qualer.com/Company/Employees) on Qualer.

    ![alt text](image.png)

    Contact Jeff or Johnny if you need these credentials.



2. Edit `config.yaml` to configure watched folders, API endpoints, and other settings:

    ```yaml
    max_runtime: null          # null = run forever, or seconds
    live_api: true             # false = use staging endpoint
    debug: false               # true = skip actual uploads
    delete_mode: false         # true = delete processed files, false = archive

    sharepoint_path: "~/Johnson Gage and Inspection, Inc/..."
    log_file: "{sharepoint_path}Logs/pdfUploader.log"
    po_dict_file: "{sharepoint_path}Logs/DoNotMoveThisFile.json.gz"

    watched_folders:
      - input_dir: "{sharepoint_path}!!! Front Office Scanned Docs - HOLDING"
        output_dir: "{sharepoint_path}!!! Front Office Scanned Docs - HOLDING/Archives"
        reject_dir: "{sharepoint_path}!!! Front Office Scanned Docs - HOLDING/No_Order_Found"
        qualer_document_type: "General"
        validate_po: true      # Enable PO price validation for this folder
      - input_dir: "{sharepoint_path}!!! Scanned External Certs"
        output_dir: "{sharepoint_path}!!! Scanned External Certs/Archives"
        reject_dir: "{sharepoint_path}!!! Scanned External Certs/No_Order_Found"
        qualer_document_type: "ordercertificate"
        validate_po: false
    ```

    Paths support `~` expansion and `{sharepoint_path}` interpolation.

---

## Usage

### Starting the program

Choose one:

+ **GUI mode** (default for `.exe`):

    ```sh
    python watcher.py --gui
    ```

    or simply run the compiled executable:

    ```sh
    PDF_Uploader.exe
    ```

+ **CLI mode** (default when running from source):

    ```sh
    python watcher.py
    ```

    or explicitly:

    ```sh
    python watcher.py --cli
    ```

### Operation Overview

The `pdf_uploader` script automates the processing and categorization of scanned PDF files based on their filenames, content, and designated scanner output paths.


1. **Scanner Configuration** (As of _1/18/25_):

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
     - **Purchase Orders (POs)**: Files starting with `PO` — looked up against the PO dictionary and uploaded to all matching service orders. Optionally validated against Qualer work items for price accuracy.

     - **Work Orders**: Files containing work order numbers in the filename or body — looked up via the API and uploaded to the matching service order.



3. **File Processing Logic**:

   - The script scans the file path and content to determine the document type:

     - Files with filenames starting with `PO` are treated as purchase orders and uploaded to all matching service orders.

     - Other files are scanned for work order numbers in the filename and body text.

     - An atomic **claim-by-move** ensures only one instance processes each file when multiple machines watch the same OneDrive folder.

   - The filename is adjusted as needed to resolve conflicts or provide additional context.



4. **PO Validation** (when `validate_po: true`):

   - After uploading a PO document, line items are extracted and compared against Qualer work items.

   - An annotated PDF is generated showing pass/fail status, price mismatches, and missing items.

   - The annotated PDF is uploaded as a private document.

   - Results are displayed in the GUI dashboard's detail dialog.



5. **Error Handling and Upload**:

   - If a file cannot be uploaded due to naming conflicts, content mismatches, or system errors, the script logs the issue for review.

   - File locking (OneDrive sync, antivirus) is handled with retry logic.

   - The observer thread is protected from crashes to keep monitoring after errors.

   - Successfully processed files are archived or moved based on their outcome.



6. **Automatic Reorganization**:

   - Processed files are moved to designated directories:
     - **Accepted Files**: Stored in an archive directory after successful uploads.

     - **Rejected Files**: Stored in a rejection directory for further investigation.

---

##  Contributing

- **💬 [Join the Discussions](https://github.com/Johnson-Gage-Inspection-Inc/pdf_uploader/discussions)**: Share your insights, provide feedback, or ask questions.
- **🐛 [Report Issues](https://github.com/Johnson-Gage-Inspection-Inc/pdf_uploader/issues)**: Submit bugs found or log feature requests for the `pdf_uploader` project.
- **💡 [Submit Pull Requests](https://github.com/Johnson-Gage-Inspection-Inc/pdf_uploader/blob/main/CONTRIBUTING.md)**: Review open PRs, and submit your own PRs.

<details closed>
<summary>Contributing Guidelines</summary>

1. **Fork the Repository**: Start by forking the project repository to your github account.
2. **Clone Locally**: Clone the forked repository to your local machine using a git client.
   ```sh
   git clone https://github.com/Johnson-Gage-Inspection-Inc/pdf_uploader
   ```
3. **Create a New Branch**: Always work on a new branch, giving it a descriptive name.
   ```sh
   git checkout -b new-feature-x
   ```
4. **Make Your Changes**: Develop and test your changes locally.
5. **Commit Your Changes**: Commit with a clear message describing your updates.
   ```sh
   git commit -m 'Implemented new feature x.'
   ```
6. **Push to github**: Push the changes to your forked repository.
   ```sh
   git push origin new-feature-x
   ```
7. **Submit a Pull Request**: Create a PR against the original project repository. Clearly describe the changes and their motivations.
8. **Review**: Once your PR is reviewed and approved, it will be merged into the main branch. Congratulations on your contribution!
</details>

<details closed>
<summary>Contributor Graph</summary>
<br>
<p align="left">
   <a href="https://github.com/Johnson-Gage-Inspection-Inc/pdf_uploader/graphs/contributors">
      <img src="https://contrib.rocks/image?repo=Johnson-Gage-Inspection-Inc/pdf_uploader">
   </a>
</p>
</details>

---

##  Acknowledgments

- Johnny's Brother, Jeff Hall

---
````
