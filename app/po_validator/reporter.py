"""
Reporting for PO validation results.

Phase 1: console/log
Phase 2: JSON/CSV report file
Phase 3 (future): Qualer status update, email alerts
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

from .models import ValidationResult

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Phase 1 — Console output
# ------------------------------------------------------------------


def print_result(result: ValidationResult) -> None:
    """Pretty-print a single validation result to the console."""
    icon = {
        "pass": "PASS",
        "fail": "FAIL",
        "no_pricing": "NO_PRICING",
        "extraction_failed": "EXTRACTION_FAILED",
    }.get(result.status, "???")

    header = (
        f"[{icon}] {result.document_name}"
        f"  PO# {result.po_number or '(unknown)'}"
        f"  ({result.extraction_method}, "
        f"conf={result.confidence:.0%})"
    )
    print(header)

    if result.mismatches:
        for m in result.mismatches:
            print(
                f"  MISMATCH  S/N {m.serial_number}: "
                f"PO ${m.po_price:,.2f} vs "
                f"Qualer ${m.expected_price:,.2f} "
                f"(diff ${m.difference:+,.2f})"
            )
    if result.missing_items:
        for mi in result.missing_items:
            price_str = (
                f"${mi.expected_price:,.2f}" if mi.expected_price is not None else "n/a"
            )
            print(
                f"  MISSING   S/N {mi.serial_number}: "
                f"{mi.asset_name} "
                f"(Qualer price {price_str})"
            )
    if result.status == "pass":
        extra = result.po_line_items_total - result.line_items_matched
        extra_note = f"  ({extra} unmatched PO line(s), e.g. travel)" if extra else ""
        print(
            f"  All {result.line_items_matched} Qualer work item(s) "
            f"verified on PO{extra_note}"
        )
    if result.notes:
        print(f"  Note: {result.notes}")

    print()


def print_summary(results: list[ValidationResult]) -> None:
    """Print a summary line after all POs are processed."""
    total = len(results)
    passed = sum(1 for r in results if r.status == "pass")
    failed = sum(1 for r in results if r.status == "fail")
    no_price = sum(1 for r in results if r.status == "no_pricing")
    errors = sum(1 for r in results if r.status == "extraction_failed")
    print("=" * 60)
    print(
        f"SUMMARY: {total} POs checked — "
        f"{passed} passed, {failed} FAILED, "
        f"{no_price} no pricing, {errors} extraction errors"
    )
    print("=" * 60)


# ------------------------------------------------------------------
# Phase 2 — File reports
# ------------------------------------------------------------------


def save_json_report(
    results: list[ValidationResult],
    path: str | Path = "validation_report.json",
) -> None:
    """Append results to a JSON report file."""
    p = Path(path)
    existing: list = []
    if p.exists():
        try:
            existing = json.loads(p.read_text())
        except Exception:
            pass

    existing.extend(r.model_dump(mode="json") for r in results)
    p.write_text(json.dumps(existing, indent=2, default=str))
    logger.info("Saved %d results to %s", len(results), p)


def save_csv_report(
    results: list[ValidationResult],
    path: str | Path = "validation_report.csv",
) -> None:
    """Append results to a CSV report file."""
    p = Path(path)
    write_header = not p.exists()

    fieldnames = [
        "timestamp",
        "document_name",
        "po_number",
        "service_order_id",
        "status",
        "extraction_method",
        "confidence",
        "work_items_total",
        "line_items_checked",
        "line_items_matched",
        "mismatches",
        "missing_items",
        "notes",
    ]

    with open(p, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        for r in results:
            mismatch_str = "; ".join(
                f"{m.serial_number}: ${m.po_price} vs ${m.expected_price}"
                for m in r.mismatches
            )
            missing_str = "; ".join(
                f"{mi.serial_number} ({mi.asset_name})" for mi in r.missing_items
            )
            writer.writerow(
                {
                    "timestamp": r.timestamp.isoformat(),
                    "document_name": r.document_name,
                    "po_number": r.po_number,
                    "service_order_id": r.service_order_id,
                    "status": r.status,
                    "extraction_method": r.extraction_method,
                    "confidence": f"{r.confidence:.2f}",
                    "work_items_total": r.work_items_total,
                    "line_items_checked": r.line_items_checked,
                    "line_items_matched": r.line_items_matched,
                    "mismatches": mismatch_str,
                    "missing_items": missing_str,
                    "notes": r.notes,
                }
            )
    logger.info("Appended %d results to %s", len(results), p)
