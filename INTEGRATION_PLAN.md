# PO Validator Integration Plan

## Overview

Integrate the [po-validator](https://github.com/rhythmatician/po-validator) into
[pdf_uploader](https://github.com/Johnson-Gage-Inspection-Inc/pdf_uploader) so that
PO PDFs are automatically validated against Qualer work items at scan time, annotated
with pass/fail stamps, and the annotated version uploaded back to Qualer.

## Decisions Made

| Decision | Choice |
|----------|--------|
| Upload annotated PDF | Yes — upload to Qualer as a "general" document |
| Auth approach | Use `qualer-sdk` (API key) — migrate pdf_uploader away from requests |
| Validation scope | Per-folder config (`VALIDATE_PO` flag in CONFIG entries) |
| Deployment | Bundle everything into single PyInstaller `.exe` |

## Prerequisites (Completed)

- **SDK PR #105**: qualer-sdk upload endpoints now correctly send multipart/form-data
- **pdf_uploader PR #16** (`refactor/qualer_sdk` branch): pdf_uploader migrated from
  raw `requests` to `qualer-sdk` with `app/qualer_client.py` singleton

## Architecture

### po-validator modules to copy → `app/po_validator/`

| Source file | Destination | Changes |
|-------------|-------------|---------|
| `models.py` | `app/po_validator/models.py` | None |
| `extractor.py` | `app/po_validator/extractor.py` | Fix imports to use relative |
| `annotator.py` | `app/po_validator/annotator.py` | Fix imports; resolve stamp paths via `_get_stamps_dir()` for PyInstaller |
| `reporter.py` | `app/po_validator/reporter.py` | Fix imports to use relative |
| `main.py::validate()` | `app/po_validator/__init__.py` | Extract `validate()` and helpers; accept work_items as parameter (no SDK calls inside) |

### Files NOT copied (handled by pdf_uploader)

- `client.py` → `app/qualer_client.py` already exists
- `main.py::main()` → orchestration replaced by `upload.py` integration
- `cassette.py` → test-only HTTP recorder
- `price_lookup.py` → not wired in yet
- `state.json` → polling not needed (event-driven via watcher)

### stamps/ directory

Copy `stamps/*.png` (Approved, Rejected, Inconclusive) to `app/po_validator/stamps/`.
Update PyInstaller spec to bundle them.

## Integration Points

### `app/config.py`

Add `VALIDATE_PO` boolean to each CONFIG entry:

```python
CONFIG = [
    {
        "INPUT_DIR": ...,
        "OUTPUT_DIR": ...,
        "REJECT_DIR": ...,
        "QUALER_DOCUMENT_TYPE": "General",
        "VALIDATE_PO": True,  # ← NEW
    },
    {
        "INPUT_DIR": ...,
        "OUTPUT_DIR": ...,
        "REJECT_DIR": ...,
        "QUALER_DOCUMENT_TYPE": "ordercertificate",
        "VALIDATE_PO": False,  # ← NEW
    },
]
```

### `app/api.py`

Add `get_work_items(service_order_id)` function using qualer-sdk:

```python
from qualer_sdk.api.service_order_items import get_work_items as _get_work_items

def get_work_items(service_order_id: int):
    return _get_work_items.sync(service_order_id, client=make_qualer_client())
```

### `upload.py`

After successful PO upload in `handle_po_upload()`, if `VALIDATE_PO` is enabled:

1. Read PDF bytes from filepath
2. For each serviceOrderId the PO was uploaded to:
   - Fetch work items via `api.get_work_items(serviceOrderId)`
   - Call `validate_and_annotate(pdf_bytes, serviceOrderId, work_items, document_name)`
   - Upload annotated PDF bytes to Qualer as "general" document
3. Wrap in try/except — validation failures must not block the upload flow

### `.env` additions

```
GEMINI_API_KEY=<your-key-here>
```

(`QUALER_API_KEY` already exists from PR #16)

## po-validator Source Summary

### Workflow

1. Extract line items from PO PDF (Tier 1: pdfplumber tables + regex; Tier 2: Gemini vision if confidence < 0.7)
2. Match extracted items to Qualer work items by serial number (fuzzy: case-insensitive, ignore dashes/spaces/leading zeros, substring containment)
3. Compare prices within ±$0.01 tolerance
4. Annotate PDF with ✓/✗/⚠ icons and Approved/Rejected/Inconclusive stamp
5. Return annotated PDF bytes and ValidationResult

### Key Models (Pydantic v2)

- `POLineItem` — serial_number, description, unit_price, quantity, extended_price, page_number, bbox
- `POExtraction` — po_number, line_items, confidence, extraction_method, raw_text
- `PriceMismatch` — serial_number, po_price, expected_price, difference
- `MissingWorkItem` — work_item_id, serial_number, asset_name, expected_price
- `LineAnnotation` — status, comment, page_number, bbox, search_text
- `ValidationResult` — document_name, po_number, service_order_id, status, mismatches, missing_items, annotations, ...

### Validation Statuses

- `pass` — all work items found, all prices match
- `fail` — price mismatch or missing work items
- `no_pricing` — PO has items but no prices (acceptable per policy)
- `extraction_failed` — couldn't parse PDF or no work items in Qualer
- `skipped` — outbound price-update request, not a customer PO

### Dependencies

- `pdfplumber>=0.11` — Tier 1 extraction
- `google-genai>=1.0` — Tier 2 LLM extraction (Gemini 2.0 Flash)
- `PyMuPDF>=1.24` — PDF annotation (already in pdf_uploader requirements)
- `pydantic>=2.0` — data models
- `python-dotenv>=1.0` — .env loading (already in pdf_uploader)
