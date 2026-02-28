"""
PO Validator — validates Purchase Order PDFs against Qualer work items.

This sub-package extracts line items from PO PDFs and compares prices
against the expected service charges from Qualer.  It annotates the PDF
with pass/fail icons and stamps, returning the annotated bytes and a
structured ValidationResult.

Usage from pdf_uploader:

    from app.po_validator import validate_and_annotate
    annotated_bytes, filename, result = validate_and_annotate(
        pdf_bytes=raw_pdf,
        service_order_id=12345,
        work_items=work_items_from_qualer,
        document_name="PO_53105.pdf",
    )
"""

from __future__ import annotations

import io
import logging
import re
import pdfplumber

from .annotator import annotate_pdf
from .extractor import extract_po_data
from .models import (
    LineAnnotation,
    MissingWorkItem,
    POLineItem,
    PriceMismatch,
    ValidationResult,
)
from .reporter import print_result

logger = logging.getLogger(__name__)

# Tolerance for price comparison (±)
PRICE_TOLERANCE = 0.01


def _search_text_for(item: POLineItem, wi_serial: str | None = None) -> str:
    """Build fallback search text for a PO line item.

    Prefer the PO serial number (most unique), then the work-item serial
    number (if supplied), then the item description.
    """
    if item.serial_number:
        return item.serial_number
    if wi_serial:
        return wi_serial
    return item.description or ""


def _normalise_sn(sn: str) -> str:
    """Normalise a serial number for matching: uppercase, strip whitespace."""
    return sn.strip().upper().replace("-", "").replace(" ", "")


def _match_sn(sn1: str, sn2: str) -> bool:
    """Fuzzy-match two serial numbers (ignore case, dashes, spaces, leading zeros)."""
    a = _normalise_sn(sn1)
    b = _normalise_sn(sn2)
    if a == b:
        return True
    # Try stripping leading zeros
    if a.lstrip("0") == b.lstrip("0"):
        return True
    # Check if one contains the other (partial match)
    if len(a) >= 4 and len(b) >= 4:
        if a in b or b in a:
            return True
    return False


def validate(
    pdf_content: bytes,
    service_order_id: int,
    work_items: list,
    document_name: str = "",
) -> ValidationResult:
    """
    Extract line items from a PO PDF and compare prices against
    Qualer work items for the same service order.

    Each Qualer work item (identified by serial_number) should appear
    as a line item on the PO.  Prices are compared against
    service_charge from Qualer.

    Args:
        pdf_content: Raw PDF bytes.
        service_order_id: Qualer service order ID.
        work_items: List of Qualer work item objects (SDK models).
        document_name: Original filename for reporting.

    Returns a ValidationResult with status:
      - "pass"               all prices match and no items missing
      - "fail"               price mismatch or missing work items
      - "no_pricing"         PO has line items but no prices listed
      - "extraction_failed"  could not parse the PDF
      - "skipped"            outbound price-update request, not a real PO
    """
    if not work_items:
        return ValidationResult(
            document_name=document_name,
            service_order_id=service_order_id,
            status="extraction_failed",
            notes="No work items found in Qualer for this order",
        )

    # Build a list of (normalised_key, work_item) for items with S/Ns.
    # Uses a list (not a dict) so duplicate S/Ns are preserved.
    wi_entries: list[tuple[str, object]] = []
    for wi in work_items:
        if wi.serial_number:
            wi_entries.append((_normalise_sn(wi.serial_number), wi))
        if (
            wi.service_charge is not None
            and wi.service_total is not None
            and wi.service_charge != wi.service_total
        ):
            logger.info(
                "Work item %s (S/N %s): service_charge=$%.2f != service_total=$%.2f",
                wi.work_item_id,
                wi.serial_number,
                wi.service_charge,
                wi.service_total,
            )

    # ---- Quick content check: skip outbound price-update requests ----
    try:
        with pdfplumber.open(io.BytesIO(pdf_content)) as _quick_pdf:
            _first_text = (
                (_quick_pdf.pages[0].extract_text() or "") if _quick_pdf.pages else ""
            )
        if (
            "order price update" in _first_text.lower()
            and "request for po" in _first_text.lower()
        ):
            logger.info("Skipping price-update request (detected in PDF content)")
            return ValidationResult(
                document_name=document_name,
                service_order_id=service_order_id,
                status="skipped",
                notes="Document is an outbound price-update request, not a customer PO",
            )
    except Exception:
        pass  # If quick check fails, proceed with normal extraction

    # ---- Extract PO data from PDF ----
    extraction = extract_po_data(pdf_content)

    if not extraction.line_items:
        return ValidationResult(
            document_name=document_name,
            po_number=extraction.po_number,
            service_order_id=service_order_id,
            status="extraction_failed",
            extraction_method=extraction.extraction_method,
            confidence=extraction.confidence,
            work_items_total=len(work_items),
            notes="No line items could be extracted from PO",
        )

    # ---- Check if the PO contains any pricing at all ----
    has_any_price = any(
        item.unit_price is not None or item.extended_price is not None
        for item in extraction.line_items
    )
    if not has_any_price:
        return ValidationResult(
            document_name=document_name,
            po_number=extraction.po_number,
            service_order_id=service_order_id,
            status="no_pricing",
            line_items_checked=len(extraction.line_items),
            work_items_total=len(work_items),
            extraction_method=extraction.extraction_method,
            confidence=extraction.confidence,
            notes="PO contains no pricing — acceptable per policy",
        )

    # ---- Helper: get price from a work item or PO line ----
    def _wi_price(wi: object) -> float | None:
        charge = getattr(wi, "service_charge", None)
        total = getattr(wi, "service_total", None)
        return charge if charge is not None else total

    def _po_price(item: POLineItem) -> float | None:
        return item.unit_price if item.unit_price is not None else item.extended_price

    # ==================================================================
    # Phase 1 — Match by S/N using elimination (best price match first)
    # ==================================================================
    mismatches: list[PriceMismatch] = []
    annotations: list[LineAnnotation] = []
    checked = 0
    matched_count = 0
    matched_wi_idxs: set[int] = set()  # indices into wi_entries
    matched_po_idxs: set[int] = set()  # indices into extraction.line_items

    # (|diff|, wi_idx, po_idx, expected, po_price)
    candidates: list[tuple[float, int, int, float, float]] = []
    for wi_idx, (wi_key, wi) in enumerate(wi_entries):
        expected = _wi_price(wi)
        if expected is None:
            continue
        for po_idx, po_item in enumerate(extraction.line_items):
            if not po_item.serial_number:
                continue
            if not _match_sn(po_item.serial_number, wi_key):
                continue
            po_p = _po_price(po_item)
            if po_p is None:
                continue
            candidates.append((abs(po_p - expected), wi_idx, po_idx, expected, po_p))

    candidates.sort()  # smallest price difference first

    for _, wi_idx, po_idx, expected, po_p in candidates:
        if wi_idx in matched_wi_idxs or po_idx in matched_po_idxs:
            continue
        matched_wi_idxs.add(wi_idx)
        matched_po_idxs.add(po_idx)
        wi = wi_entries[wi_idx][1]
        po_item = extraction.line_items[po_idx]
        checked += 1
        diff = po_p - expected
        if abs(diff) <= PRICE_TOLERANCE:
            matched_count += 1
            annotations.append(
                LineAnnotation(
                    status="ok",
                    comment="",
                    page_number=po_item.page_number,
                    bbox=po_item.bbox,
                    search_text=_search_text_for(
                        po_item, getattr(wi, "serial_number", None)
                    ),
                )
            )
        else:
            mismatches.append(
                PriceMismatch(
                    serial_number=po_item.serial_number
                    or getattr(wi, "serial_number", "")
                    or "",
                    po_price=po_p,
                    expected_price=expected,
                    difference=round(diff, 2),
                    description=po_item.description,
                    work_item_id=getattr(wi, "work_item_id", None),
                )
            )
            annotations.append(
                LineAnnotation(
                    status="mismatch",
                    comment=f"Expected ${expected:,.2f}, PO says ${po_p:,.2f}",
                    page_number=po_item.page_number,
                    bbox=po_item.bbox,
                    search_text=_search_text_for(
                        po_item, getattr(wi, "serial_number", None)
                    ),
                )
            )

    # ==================================================================
    # Phase 2 — Fallback: match remaining work items by text/description
    # ==================================================================
    raw_text = extraction.raw_text or ""

    for wi_idx, (wi_key, wi) in enumerate(wi_entries):
        if wi_idx in matched_wi_idxs:
            continue

        sn_str = getattr(wi, "serial_number", "") or ""
        asset = (
            getattr(wi, "asset_name", "") or getattr(wi, "asset_description", "") or ""
        )

        # Build search variants: original S/N + version without parenthetical
        sn_variants = [sn_str] if sn_str else []
        base_sn = re.sub(r"\s*\([^)]*\)", "", sn_str).strip()
        if base_sn and base_sn != sn_str:
            sn_variants.append(base_sn)

        # Search raw text
        found_in_text = any(v in raw_text for v in sn_variants) or (
            asset and asset.lower() in raw_text.lower()
        )
        # Also search PO line item descriptions
        if not found_in_text:
            for po_item in extraction.line_items:
                desc = po_item.description or ""
                if any(v in desc for v in sn_variants) or (
                    asset and asset.lower() in desc.lower()
                ):
                    found_in_text = True
                    break
        if not found_in_text:
            continue

        expected = _wi_price(wi)
        if expected is None:
            continue

        best_po_idx: int | None = None
        best_diff: float = float("inf")
        for po_idx, po_item in enumerate(extraction.line_items):
            if po_idx in matched_po_idxs:
                continue
            po_p = _po_price(po_item)
            if po_p is None:
                continue
            d = abs(po_p - expected)
            if d < best_diff:
                best_diff = d
                best_po_idx = po_idx

        if best_po_idx is not None:
            matched_wi_idxs.add(wi_idx)
            matched_po_idxs.add(best_po_idx)
            po_item = extraction.line_items[best_po_idx]
            po_p = _po_price(po_item)
            assert po_p is not None
            checked += 1
            diff = po_p - expected
            if abs(diff) <= PRICE_TOLERANCE:
                matched_count += 1
                annotations.append(
                    LineAnnotation(
                        status="ok",
                        comment="",
                        page_number=po_item.page_number,
                        bbox=po_item.bbox,
                        search_text=_search_text_for(po_item, sn_str),
                    )
                )
            else:
                mismatches.append(
                    PriceMismatch(
                        serial_number=sn_str,
                        po_price=po_p,
                        expected_price=expected,
                        difference=round(diff, 2),
                        description=po_item.description,
                        work_item_id=getattr(wi, "work_item_id", None),
                    )
                )
                annotations.append(
                    LineAnnotation(
                        status="mismatch",
                        comment=f"Expected ${expected:,.2f}, PO says ${po_p:,.2f}",
                        page_number=po_item.page_number,
                        bbox=po_item.bbox,
                        search_text=_search_text_for(po_item, sn_str),
                    )
                )

    # ---- Check for Qualer work items missing from the PO ----
    missing_items: list[MissingWorkItem] = []
    for wi_idx, (_wi_key, wi) in enumerate(wi_entries):
        if wi_idx not in matched_wi_idxs:
            missing_items.append(
                MissingWorkItem(
                    work_item_id=getattr(wi, "work_item_id", 0) or 0,
                    serial_number=getattr(wi, "serial_number", "") or "",
                    asset_name=getattr(wi, "asset_name", "") or "",
                    expected_price=_wi_price(wi),
                )
            )

    # ---- Unverified annotations for unmatched PO line items ----
    for po_idx, po_item in enumerate(extraction.line_items):
        if po_idx not in matched_po_idxs:
            # Only annotate items that have a price (skip travel/misc)
            if _po_price(po_item) is not None:
                annotations.append(
                    LineAnnotation(
                        status="unverified",
                        comment="Not matched to a Qualer work item",
                        page_number=po_item.page_number,
                        bbox=po_item.bbox,
                        search_text=_search_text_for(po_item),
                    )
                )

    # ---- Determine overall status ----
    has_problems = bool(mismatches) or bool(missing_items)
    final_status: str = "fail" if has_problems else "pass"

    notes_parts: list[str] = []
    if missing_items:
        notes_parts.append(f"{len(missing_items)} work item(s) not found on PO")
    if not checked and not mismatches:
        notes_parts.append("No S/N matches found between PO and Qualer")

    return ValidationResult(
        document_name=document_name,
        po_number=extraction.po_number,
        service_order_id=service_order_id,
        status=final_status,  # type: ignore[arg-type]
        mismatches=mismatches,
        missing_items=missing_items,
        annotations=annotations,
        po_line_items_total=len(extraction.line_items),
        line_items_checked=checked,
        line_items_matched=matched_count,
        work_items_total=len(work_items),
        extraction_method=extraction.extraction_method,
        confidence=extraction.confidence,
        notes="; ".join(notes_parts) if notes_parts else "",
    )


def validate_and_annotate(
    pdf_bytes: bytes,
    service_order_id: int,
    work_items: list,
    document_name: str = "",
) -> tuple[bytes | None, str, ValidationResult]:
    """
    Validate a PO PDF against Qualer work items and produce an annotated PDF.

    This is the main entry point for the PO validation sub-package.

    Args:
        pdf_bytes: Raw PDF file content.
        service_order_id: Qualer service order ID.
        work_items: Qualer work item objects for the service order.
        document_name: Original filename (used for output naming).

    Returns:
        A tuple of (annotated_pdf_bytes, output_filename, ValidationResult).
        annotated_pdf_bytes is None if annotation fails or the document was skipped.
    """
    # Validate
    result = validate(
        pdf_content=pdf_bytes,
        service_order_id=service_order_id,
        work_items=work_items,
        document_name=document_name,
    )

    print_result(result)

    if result.status == "skipped":
        return None, "", result

    # Annotate
    try:
        annotated_bytes, annotated_name = annotate_pdf(pdf_bytes, result)
        logger.info("Annotated PDF generated: %s", annotated_name)
        return annotated_bytes, annotated_name, result
    except Exception:
        logger.exception("Failed to annotate %s", document_name)
        return None, "", result
