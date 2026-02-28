"""
Two-tier PO PDF extraction: pdfplumber (table-based) with LLM fallback.

Tier 1 – pdfplumber: fast, free, works well on digitally-generated PDFs and
         scans that already have a Tesseract OCR text layer.
Tier 2 – Google Gemini vision: handles arbitrary layouts, handwritten notes,
         and low-quality scans.  Only invoked when Tier 1 yields low confidence.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import re
from os import getenv
from typing import Any
from google.genai import types, Client as GenAIClient

import pdfplumber

from .models import POExtraction, POLineItem

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CONFIDENCE_THRESHOLD = 0.7  # below this → fall back to LLM

# Patterns used to locate relevant columns in extracted tables
_SN_HEADER_PATTERNS = re.compile(r"(?i)\b(serial\s*(?:#|number|no\.?)?|s/?n)\b")
_PRICE_HEADER_PATTERNS = re.compile(
    r"(?i)\b(unit\s*price|price|rate|amount"
    r"|ext(?:ended)?\.?\s*(?:price|amt)?|total|each)\b"
)
_QTY_HEADER_PATTERNS = re.compile(r"(?i)\b(qty|quantity|qty\.?)\b")
_DESC_HEADER_PATTERNS = re.compile(
    r"(?i)\b(desc(?:ription)?|item|service|part|detail|product)\b"
)

# Pattern to extract serial numbers embedded in description text
# Matches: SN:J530199, S/N HDCC000017632, (SN: M21400189),
#          (Yokogawa SN: T16709667728), SN 305939
_SN_IN_TEXT = re.compile(
    r"(?i)(?:s/?n[:#]?\s*|serial\s*(?:#|no\.?)?:?\s*)" r"([A-Z0-9][A-Z0-9_.\-]{2,30})"
)


# ---------------------------------------------------------------------------
# Tier 1 – pdfplumber table extraction
# ---------------------------------------------------------------------------


def _find_column_index(headers: list[str], pattern: re.Pattern) -> int | None:
    """Return the index of the first header matching *pattern*, or None."""
    for i, h in enumerate(headers):
        if h and pattern.search(h):
            return i
    return None


def _clean_price(raw: str | None) -> float | None:
    """Parse a price string like '$1,234.56' into a float."""
    if not raw:
        return None
    cleaned = re.sub(r"[^\d.\-]", "", str(raw))
    try:
        return float(cleaned)
    except ValueError:
        return None


class _PageTable:
    """A table extracted from a specific page, with spatial data."""

    __slots__ = ("page_index", "table_bbox", "cells", "data")

    def __init__(
        self,
        page_index: int,
        table_bbox: tuple[float, float, float, float],
        cells: list[tuple[float, float, float, float]],
        data: list[list[str | None]],
    ):
        self.page_index = page_index
        self.table_bbox = table_bbox
        self.cells = cells
        self.data = data


def _extract_tables_from_pages(pdf: Any) -> list[_PageTable]:
    """Extract all tables from all pages, preserving page index and bbox."""
    all_tables: list[_PageTable] = []
    for page_idx, page in enumerate(pdf.pages):
        found = page.find_tables()
        for tbl in found:
            data = tbl.extract()
            if data:
                all_tables.append(
                    _PageTable(
                        page_index=page_idx,
                        table_bbox=tuple(tbl.bbox),  # type: ignore[arg-type]
                        cells=list(tbl.cells) if tbl.cells else [],
                        data=data,
                    )
                )
    return all_tables


class _PageText:
    """Raw text for a single page with its page index."""

    __slots__ = ("page_index", "text")

    def __init__(self, page_index: int, text: str):
        self.page_index = page_index
        self.text = text


def _extract_text_from_pages(pdf: Any) -> tuple[str, list[_PageText]]:
    """Extract full text and per-page text from all pages."""
    pages: list[_PageText] = []
    for page_idx, page in enumerate(pdf.pages):
        text = page.extract_text()
        if text:
            pages.append(_PageText(page_index=page_idx, text=text))
    combined = "\n".join(pt.text for pt in pages)
    return combined, pages


# Pattern to match IP addresses (false positive for S/N)
_IP_ADDRESS = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")


def _extract_serial_from_text(text: str) -> str | None:
    """Extract a serial number embedded in description text."""
    m = _SN_IN_TEXT.search(text)
    if not m:
        return None
    sn = m.group(1).strip()
    # Reject IP addresses
    if _IP_ADDRESS.match(sn):
        return None
    return sn


def _find_po_number(text: str) -> str:
    """Try to find the PO number in raw text."""
    # Try specific formats first (most precise → least)
    patterns = [
        # "Purchase Order#20260105016PO" or "Purchase Order No: 53105"
        r"(?i)purchase\s+order\s*(?:#|no\.?:?)\s*([A-Z0-9][\w\-]{2,30})",
        # "Purchase Order 10496" — same line only, must start with digit
        r"(?i)purchase\s+order[ \t]+(\d[\w\-]{2,30})",
        # "PO Number: 160003"
        r"(?i)\bPO\s+Number\s*:?\s*([A-Z0-9][\w\-]{2,30})",
        # "PO No: TE022442" or "PO#: 12345"
        r"(?i)\bPO\s*(?:#|No\.?)\s*:?\s*([A-Z0-9][\w\-]{2,30})",
        # "Customer PO: 20260202019PO" or "Customer PO# 53057"
        r"(?i)customer\s+PO[#:]?\s+([A-Z0-9][\w\-]{2,30})",
        # "Invoice #: 56561-084498"  (for SSRS docs)
        r"(?i)invoice\s*#:?\s*(\d[\d\-]{4,30})",
    ]
    false_positives = {
        "VENDOR",
        "TO",
        "NUMBER",
        "NO",
        "DATE",
        "UPDATE",
        "REQUEST",
        "DETERMINED",
        "HOLD",
        "PAGE",
        "CUSTOMER",
    }
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            val = m.group(1).strip()
            if val.upper() in false_positives:
                continue
            return val
    return ""


def _find_header_row(table: list[list[str | None]]) -> int:
    """Find the row that best matches a header row (most recognised columns)."""
    all_patterns = [
        _SN_HEADER_PATTERNS,
        _PRICE_HEADER_PATTERNS,
        _QTY_HEADER_PATTERNS,
        re.compile(r"(?i)\b(desc(?:ription)?|product|service|detail)\b"),
    ]
    best_row = 0
    best_score = 0
    for ri, row in enumerate(table[: min(len(table), 8)]):
        score = 0
        for cell in row:
            if not cell:
                continue
            s = str(cell).strip()
            for p in all_patterns:
                if p.search(s):
                    score += 1
                    break
        if score > best_score:
            best_score = score
            best_row = ri
    return best_row


def _find_desc_column_index(headers: list[str]) -> int | None:
    """Find the description column with priority matching.

    Avoids matching 'Line\\nItem', 'Item No', 'Supplier Part No', etc.
    """
    # Priority 1: explicit "description" or "product"
    for i, h in enumerate(headers):
        if h and re.search(r"(?i)\b(desc(?:ription)?|product)\b", h):
            return i
    # Priority 2: "service", "detail"
    for i, h in enumerate(headers):
        if h and re.search(r"(?i)\b(service|detail)\b", h):
            return i
    # Priority 3: "item" but NOT "line item" / "item no" / "item #"
    for i, h in enumerate(headers):
        if not h:
            continue
        norm = re.sub(r"\s+", " ", h)
        if re.search(r"(?i)\bitem\b", norm) and not re.search(
            r"(?i)(line|#|no\.?|number)", norm
        ):
            return i
    return None


# Rows matching this pattern are subtotal / tax / routing lines
_SKIP_ROW_PAT = re.compile(
    r"(?i)(sub\s*total|grand\s*total|\btotal\b" r"|full\s*tax|withheld|route\s*to)"
)


def _parse_table(
    page_table: _PageTable,
) -> tuple[list[POLineItem], float]:
    """
    Attempt to parse a single table into POLineItems.

    Returns (items, confidence).  Confidence is based on how many expected
    columns were found and how many rows yielded usable data.
    """
    table = page_table.data
    cells = page_table.cells

    if not table or len(table) < 2:
        return [], 0.0

    # Find the real header row (may not be row 0)
    hdr_idx = _find_header_row(table)
    if hdr_idx >= len(table) - 1:  # no data rows after header
        return [], 0.0

    raw_headers = [str(cell).strip() if cell else "" for cell in table[hdr_idx]]

    sn_idx = _find_column_index(raw_headers, _SN_HEADER_PATTERNS)
    price_idx = _find_column_index(raw_headers, _PRICE_HEADER_PATTERNS)
    qty_idx = _find_column_index(raw_headers, _QTY_HEADER_PATTERNS)
    desc_idx = _find_desc_column_index(raw_headers)

    # We need at least a price OR serial-number column to be useful
    if price_idx is None and sn_idx is None:
        return [], 0.0

    # Build a mapping from row_index → row bbox.
    # pdfplumber cells are NOT guaranteed row-major; they may be
    # column-major (sorted by x then y).  We group cells by their
    # y-coordinate (top edge) using a tolerance to handle rounding.
    row_bboxes: dict[int, tuple[float, float, float, float]] = {}
    if cells:
        # 1) Collect unique y-top values with tolerance grouping
        y_tops: list[float] = sorted({round(c[1], 1) for c in cells})
        # Merge y values within 2pt of each other into a single row
        merged_y: list[float] = []
        for y in y_tops:
            if merged_y and abs(y - merged_y[-1]) < 2:
                continue
            merged_y.append(y)

        # 2) Map each cell to its row index based on y-position
        def _y_to_row(y: float) -> int:
            for ri, ry in enumerate(merged_y):
                if abs(y - ry) < 2:
                    return ri
            return len(merged_y)  # fallback

        for cell_bbox in cells:
            row_i = _y_to_row(round(cell_bbox[1], 1))
            if row_i not in row_bboxes:
                row_bboxes[row_i] = cell_bbox
            else:
                prev = row_bboxes[row_i]
                row_bboxes[row_i] = (
                    min(prev[0], cell_bbox[0]),
                    min(prev[1], cell_bbox[1]),
                    max(prev[2], cell_bbox[2]),
                    max(prev[3], cell_bbox[3]),
                )

    items: list[POLineItem] = []
    for data_row_idx, row in enumerate(table[hdr_idx + 1 :]):
        if not row or all(not cell for cell in row):
            continue

        # Skip subtotal / tax / routing rows
        row_text = " ".join(str(c) for c in row if c)
        if _SKIP_ROW_PAT.search(row_text):
            continue

        # Safely index into row (tables can be ragged)
        def _cell(idx: int | None) -> str | None:
            if idx is None or idx >= len(row):
                return None
            return str(row[idx]).strip() if row[idx] else None

        sn = _cell(sn_idx)
        description = _cell(desc_idx) or ""
        # Clean multiline cell content
        description = re.sub(r"\s*\n\s*", " ", description).strip()

        # Try extracting S/N from description if no dedicated column
        if not sn and description:
            sn = _extract_serial_from_text(description)

        unit_price = _clean_price(_cell(price_idx))
        qty_raw = _cell(qty_idx)
        quantity: int | None = None
        if qty_raw:
            try:
                quantity = int(re.sub(r"[^\d]", "", qty_raw))
            except ValueError:
                pass

        # Look for a second price column (extended / total)
        extended_price: float | None = None
        if price_idx is not None:
            price_indices = [
                i
                for i, h in enumerate(raw_headers)
                if _PRICE_HEADER_PATTERNS.search(h)
                if h
            ]
            if len(price_indices) > 1 and price_indices[-1] != price_idx:
                extended_price = _clean_price(_cell(price_indices[-1]))

        # Skip rows that have no meaningful content
        if sn is None and unit_price is None and not description:
            continue

        # Compute row bbox from cell coordinates
        abs_row_idx = hdr_idx + 1 + data_row_idx
        item_bbox = row_bboxes.get(abs_row_idx)

        items.append(
            POLineItem(
                serial_number=sn,
                description=description,
                unit_price=unit_price,
                quantity=quantity,
                extended_price=extended_price,
                page_number=page_table.page_index,
                bbox=item_bbox,
            )
        )

    if not items:
        return [], 0.0

    # Score confidence
    cols_found = sum(
        1 for idx in [sn_idx, price_idx, qty_idx, desc_idx] if idx is not None
    )
    col_conf = cols_found / 4
    rows_with_sn = sum(1 for it in items if it.serial_number)
    rows_with_price = sum(1 for it in items if it.unit_price is not None)
    data_conf = (rows_with_sn + rows_with_price) / (2 * len(items)) if items else 0
    confidence = 0.5 * col_conf + 0.5 * data_conf

    return items, round(confidence, 3)


# ---------------------------------------------------------------------------
# Text-based parsing helpers
# ---------------------------------------------------------------------------


def _enrich_items_with_text_sns(items: list[POLineItem], raw_text: str) -> None:
    """
    Scan raw_text for serial numbers near item descriptions and
    attach them to items that are missing S/Ns.  Modifies in place.
    """
    all_sns = _SN_IN_TEXT.findall(raw_text)
    if not all_sns:
        return
    # Filter out IP addresses and S/Ns already assigned to other items
    assigned = {it.serial_number for it in items if it.serial_number}
    valid = [
        sn.strip()
        for sn in all_sns
        if not _IP_ADDRESS.match(sn.strip()) and sn.strip() not in assigned
    ]
    sn_iter = iter(valid)
    for item in items:
        if item.serial_number:
            continue
        sn = next(sn_iter, None)
        if sn:
            item.serial_number = sn


_SKIP_LINE_PAT = re.compile(
    r"(?i)(sub\s*tota[il]|grand\s*total|order\s*total"
    r"|\btotal\s*:|^total$|^tax\b|^shipping\b|^freight\b"
    r"|comments|approved\s+by)"
)


def _parse_text_lines(page_texts: list[_PageText]) -> list[POLineItem]:
    """
    Regex-based fallback: parse line items from raw text when
    pdfplumber's table extractor finds nothing.

    Accepts per-page text so we can record which page each item is on.
    """
    items: list[POLineItem] = []
    price_pat = re.compile(r"\$(\d[\d,.]+)")

    for pt in page_texts:
        lines = pt.text.split("\n")

        # Walk through lines, looking for price lines and nearby S/Ns
        i = 0
        while i < len(lines):
            line = lines[i]
            prices_in_line = price_pat.findall(line)
            if not prices_in_line:
                i += 1
                continue

            # Keep zero-price lines — they can be real items (e.g. warranty/CMM test)
            valid = [p for p in prices_in_line if _clean_price(p) is not None]
            if not valid:
                i += 1
                continue

            # Build wider context window for S/N extraction
            context_start = max(0, i - 2)
            context_end = min(len(lines), i + 7)
            context = "\n".join(lines[context_start:context_end])

            sn = _extract_serial_from_text(context)

            # Determine prices
            unit_price = _clean_price(valid[-1])
            ext_price = None
            if len(valid) >= 2:
                unit_price = _clean_price(valid[-2])
                ext_price = _clean_price(valid[-1])

            # Build description from current line (strip prices)
            desc = price_pat.sub("", line).strip()
            desc = re.sub(r"\s{2,}", " ", desc)[:120]

            # Grab description from next 2 non-price, non-boilerplate lines
            for j in range(i + 1, min(len(lines), i + 3)):
                nl = lines[j].strip()
                if not nl:
                    continue
                if price_pat.search(nl):
                    break
                if len(nl) > 80:  # likely boilerplate paragraph
                    break
                if _SKIP_LINE_PAT.search(nl):
                    break
                desc = (desc + " | " + nl)[:250]

            # Skip subtotal / total / tax lines
            first_part = desc.split("|")[0].strip()
            if _SKIP_LINE_PAT.search(first_part):
                i += 1
                continue

            items.append(
                POLineItem(
                    serial_number=sn,
                    description=desc,
                    unit_price=unit_price,
                    quantity=1,
                    extended_price=ext_price,
                    page_number=pt.page_index,
                    bbox=None,
                )
            )
            i += 1

    return items


def extract_with_pdfplumber(pdf_bytes: bytes) -> POExtraction | None:
    """
    Tier 1: extract PO data using pdfplumber's table detection.

    Returns a POExtraction with method='table', or None if nothing useful found.
    """
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            raw_text, page_texts = _extract_text_from_pages(pdf)
            tables = _extract_tables_from_pages(pdf)
    except Exception:
        logger.exception("pdfplumber failed to open PDF")
        return None

    if not raw_text and not tables:
        return None

    po_number = _find_po_number(raw_text)

    # Try each table; keep the best result
    best_items: list[POLineItem] = []
    best_conf = 0.0
    for tbl in tables:
        items, conf = _parse_table(tbl)
        if conf > best_conf:
            best_items, best_conf = items, conf

    # If table parsing worked well, also enrich items with S/N from
    # nearby raw text (serial numbers often appear on lines below the
    # main item row, which pdfplumber's table extractor may miss).
    if best_items:
        _enrich_items_with_text_sns(best_items, raw_text)
        return POExtraction(
            po_number=po_number,
            line_items=best_items,
            confidence=best_conf,
            extraction_method="table",
            raw_text=raw_text[:5000],
        )

    # No structured table found → try regex-based text parsing
    text_items = _parse_text_lines(page_texts)
    if text_items:
        conf = 0.5  # moderate confidence for regex parsing
        return POExtraction(
            po_number=po_number,
            line_items=text_items,
            confidence=conf,
            extraction_method="text",
            raw_text=raw_text[:5000],
        )

    # Return low-confidence result with raw text for LLM fallback
    return POExtraction(
        po_number=po_number,
        line_items=[],
        confidence=0.1,
        extraction_method="none",
        raw_text=raw_text[:5000],
    )


# ---------------------------------------------------------------------------
# Tier 2 – Google Gemini vision fallback
# ---------------------------------------------------------------------------

_LLM_SYSTEM_PROMPT = """\
You are a data-extraction assistant.  The user will show you page images of a \
Purchase Order (PO) document.  Extract ALL line items into JSON.

Return ONLY a JSON object with this schema (no markdown fences):
{
  "po_number": "<string>",
  "line_items": [
    {
      "serial_number": "<string or null>",
      "description": "<string>",
      "unit_price": <number or null>,
      "quantity": <integer or null>,
      "extended_price": <number or null>,
      "page_number": <0-based page index where this item appears>
    }
  ]
}

Rules:
- serial_number: the instrument serial number, S/N, or asset tag.  null if absent.
- unit_price: per-unit price.  null if not listed.
- extended_price: line total (qty × unit_price).  null if not listed.
- page_number: 0-based index of which page image the line item appears on.
- Omit header/footer rows, subtotals, tax lines, and shipping charges.
- INCLUDE line items with $0.00 price or zero quantity — they are real items.
- If the PO contains NO line-item pricing at all, return line items with null prices.
- Return valid JSON only.  No extra text.
"""


def _pdf_pages_to_base64_images(pdf_bytes: bytes) -> list[str]:
    """Convert each PDF page to a base64-encoded PNG using pdfplumber."""
    images: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            img = page.to_image(resolution=200)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()
            images.append(b64)
    return images


def extract_with_llm(pdf_bytes: bytes) -> POExtraction | None:
    """
    Tier 2: send page images to Google Gemini and ask it to extract line items.

    Requires GEMINI_API_KEY env var.  Returns None if the API is unavailable.
    """
    api_key = getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY not set — LLM extraction unavailable")
        return None

    client = GenAIClient(api_key=api_key)

    try:
        page_images = _pdf_pages_to_base64_images(pdf_bytes)
    except Exception:
        logger.exception("Failed to render PDF pages to images")
        return None

    # Build the content parts: system prompt + images
    prompt = _LLM_SYSTEM_PROMPT + "\n\nExtract line items from this PO:"
    parts: list = [types.Part.from_text(text=prompt)]
    for b64 in page_images:
        image_bytes = base64.b64decode(b64)
        parts.append(types.Part.from_bytes(data=image_bytes, mime_type="image/png"))

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=parts,
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=4096,
            ),
        )
        raw = response.text or ""
    except Exception:
        logger.exception("Gemini API call failed")
        return None

    # Parse the JSON response
    try:
        # Strip markdown code fences if present
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.error("LLM returned invalid JSON: %s", raw[:500])
        return None

    line_items = [
        POLineItem(
            serial_number=item.get("serial_number"),
            description=item.get("description", ""),
            unit_price=item.get("unit_price"),
            quantity=item.get("quantity"),
            extended_price=item.get("extended_price"),
            page_number=item.get("page_number"),
            bbox=None,
        )
        for item in data.get("line_items", [])
    ]

    return POExtraction(
        po_number=data.get("po_number") or "",
        line_items=line_items,
        confidence=0.9,  # LLM extractions are generally high quality
        extraction_method="llm",
        raw_text="",  # not needed for LLM path
    )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def extract_po_data(pdf_bytes: bytes) -> POExtraction:
    """
    Extract structured PO data from a PDF.

    Strategy:
      1. Try pdfplumber table extraction (fast, free).
      2. If confidence < threshold, try Google Gemini vision.
      3. Return whichever result is better, or a failed result.
    """
    # Tier 1
    table_result = extract_with_pdfplumber(pdf_bytes)
    if table_result and table_result.confidence >= CONFIDENCE_THRESHOLD:
        logger.info(
            "Tier 1 (pdfplumber) succeeded — confidence %.2f, %d items",
            table_result.confidence,
            len(table_result.line_items),
        )
        return table_result

    tier1_note = (
        f"Tier 1 confidence {table_result.confidence:.2f}"
        if table_result
        else "Tier 1 returned nothing"
    )
    logger.info("%s — trying Tier 2 (LLM)", tier1_note)

    # Tier 2
    llm_result = extract_with_llm(pdf_bytes)
    if llm_result and llm_result.line_items:
        # Carry raw_text from Tier 1 so validate() can do
        # text-based fallback matching even on LLM results.
        if table_result and table_result.raw_text:
            llm_result.raw_text = table_result.raw_text
        logger.info(
            "Tier 2 (LLM) succeeded — %d items extracted",
            len(llm_result.line_items),
        )
        return llm_result

    # Return whatever we have (might be low-confidence table result or empty)
    if table_result:
        return table_result

    return POExtraction(
        po_number="",
        line_items=[],
        confidence=0.0,
        extraction_method="none",
        raw_text="",
    )
