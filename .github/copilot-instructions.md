# PDF Uploader — Copilot Instructions

## Architecture Overview

This is a **Python 3.14** desktop app that watches directories for scanned PDF files, processes them (OCR, orientation correction, splitting), and uploads them to the **Qualer** calibration-management API. It runs as either a **PyQt6 GUI** (default for the `.exe`) or a **headless CLI**.

### Data flow

```
Scanned PDF → watcher.py (watchdog) → upload.process_file()
  → claim-by-move to _processing/ dir
  → pdf.workorders() extracts WO numbers (or PO logic for "PO*" filenames)
  → api.getServiceOrderId() → api.upload() to Qualer
  → archive or reject → EventBus emits ProcessingEvent to GUI
```

### Key modules

| Module | Role |
|--------|------|
| `watcher.py` | Entry point (`main()`). Launches CLI or GUI, spawns watcher threads per folder. |
| `upload.py` | Core processing: claim-by-move, WO/PO routing, upload, archive/reject. |
| `app/api.py` | Qualer API gateway — all SDK calls go through here. Uses `qualer_sdk`. |
| `app/config_manager.py` | YAML config loader. Dataclasses `AppConfig` and `WatchedFolder`. Secrets via `.env` (dev) or encrypted `secrets.enc` (frozen). |
| `app/config.py` | Backward-compatible facade — PEP 562 `__getattr__` delegates to `config_manager`. Has a `.pyi` stub for type checkers. |
| `app/event_bus.py` | `EventBus(QObject)` singleton with Qt signals. `None` in CLI mode. Thread-safe emit from watcher threads. |
| `app/job_queue.py` | `ThreadPoolExecutor`-backed queue (GUI mode). Singleton pattern like `event_bus`. |
| `app/po_validator/` | Sub-package: extracts PO line items (Gemini AI + pdfplumber), compares against Qualer work items, annotates PDFs with pass/fail stamps. |
| `app/qualer_client.py` | Thread-safe singleton `AuthenticatedClient` factory. Uses `QUALER_API_KEY` env var. |

## Conventions & Patterns

### Singleton pattern
`event_bus`, `job_queue`, and `qualer_client` all use a module-level singleton with `init_*()`/`get_*()` functions. `get_*()` returns `None` when not initialized (CLI mode for bus/queue). Follow this pattern for new shared resources.

### Config access
Import from `app.config` (e.g., `from app.config import DEBUG`), **not** directly from `config_manager`. The `config.py` facade uses PEP 562 `__getattr__` — add new attributes to both `config.py.__getattr__._MAP` **and** `app/config.pyi`.

### Logging
Use `app.color_print` functions (`cp.red()`, `cp.green()`, `cp.blue()`, `cp.yellow()`, `cp.white()`) instead of raw `print()` or `logging.*`. These write to console, log file, **and** GUI simultaneously.

### Error handling in upload flow
Validation/annotation failures must **never** block the upload. Wrap optional post-processing in `try/except` and log via `cp.red()`. See `_run_po_validation()` in `upload.py`.

### Multi-instance safety
Files are claimed via atomic `os.rename()` into a `_processing/` subdirectory. Always use this claim-by-move pattern; never process a file in-place. `PermissionError` retry handles OneDrive/antivirus locks.

### GUI event communication
Emit `ProcessingEvent` dataclass via `EventBus` signals for GUI updates. Always guard with `if bus := get_bus():` — the bus is `None` in CLI mode.

## Development

### Running
```bash
python watcher.py          # CLI mode (default from source)
python watcher.py --gui    # GUI mode
```

### Environment
- Requires `.env` file with `QUALER_API_KEY` (UUID) and optionally `GEMINI_API_KEY`
- Config in `config.yaml` at project root (paths use `{sharepoint_path}` interpolation)
- Type stubs for untyped deps live in `stubs/` (configured via `pyrightconfig.json` and `mypy.ini`)

### Testing
```bash
pytest                     # Run all tests
pytest tests/test_api.py   # Run specific test file
```
- Tests use `unittest.TestCase` with `unittest.mock`
- `test_upload.py` mocks **all** `app.*` modules at module level before importing `upload` — this is required because `upload.py` has side effects on import (logging setup, client init)
- `conftest.py` saves real module references and restores them after `test_upload` tests to avoid mock contamination across test files
- Set `QUALER_API_KEY` env var to a dummy UUID for tests (conftest does this automatically)

### Building
```bash
pyinstaller PDF_Uploader.spec   # Single-file windowed .exe
```
- `config.yaml` and `stamps/*.png` are bundled as data files
- `hooks/hook-qualer_sdk.py` ensures SDK assets are collected

### Type checking
Pyright (via `pyrightconfig.json`) with stubs in `stubs/`. The `app/config.pyi` stub provides type info for the dynamic `config.py` facade.
