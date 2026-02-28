"""
PDF annotation / markup for PO validation results.

Overlays green checkmarks (✓), red X's (✗), and yellow warnings (⚠) on
validated PO line items, then stamps the first page with an overall result
image (Approved / Rejected / Inconclusive).
"""

from __future__ import annotations

import logging
import os as _os
import sys
from pathlib import Path
from typing import Literal, TYPE_CHECKING

if TYPE_CHECKING:
    pass

import fitz  # PyMuPDF

from .models import ValidationResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths to stamp images
# ---------------------------------------------------------------------------


def _get_stamps_dir() -> Path:
    """Resolve the stamps directory, handling PyInstaller bundled executables."""
    # When running from a PyInstaller bundle, sys._MEIPASS points to the
    # temporary directory containing bundled data files.
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).parent
    return base / "stamps"


_STAMPS_DIR = _get_stamps_dir()
_STAMP_FILES: dict[str, Path] = {
    "APPROVED": _STAMPS_DIR / "Approved_stamp.png",
    "REJECTED": _STAMPS_DIR / "Rejected_stamp.png",
    "INCONCLUSIVE": _STAMPS_DIR / "Inconclusive_stamp.png",
}

# Font for Unicode symbols (⚠) — Segoe UI Symbol ships with Windows
_SYMBOL_FONT = _os.path.join(
    _os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "seguisym.ttf"
)

# ---------------------------------------------------------------------------
# Icon drawing helpers
# ---------------------------------------------------------------------------
# Colours (RGB 0-1)
_GREEN = (0.18, 0.70, 0.29)
_RED = (0.86, 0.14, 0.14)
_YELLOW = (0.90, 0.72, 0.10)

_ICON_SIZE = 14  # side length of the icon square in points
_ICON_MARGIN = 4  # gap between the icon and the row content
_COMMENT_FONT_SIZE = 7
_COMMENT_COLOR = _RED


def _draw_checkmark(page: fitz.Page, x: float, y_center: float) -> None:
    """Draw a green ✓ at the given position."""
    shape = page.new_shape()
    half = _ICON_SIZE / 2
    # Checkmark strokes: short stroke down-right, then long stroke up-right
    shape.draw_line(
        fitz.Point(x + 2, y_center),
        fitz.Point(x + half, y_center + half - 2),
    )
    shape.draw_line(
        fitz.Point(x + half, y_center + half - 2),
        fitz.Point(x + _ICON_SIZE - 2, y_center - half + 2),
    )
    shape.finish(color=_GREEN, width=2.5, closePath=False)
    shape.commit()


def _draw_x_mark(page: fitz.Page, x: float, y_center: float) -> None:
    """Draw a red ✗ at the given position."""
    shape = page.new_shape()
    half = _ICON_SIZE / 2
    shape.draw_line(
        fitz.Point(x + 2, y_center - half + 2),
        fitz.Point(x + _ICON_SIZE - 2, y_center + half - 2),
    )
    shape.draw_line(
        fitz.Point(x + _ICON_SIZE - 2, y_center - half + 2),
        fitz.Point(x + 2, y_center + half - 2),
    )
    shape.finish(color=_RED, width=2.5, closePath=False)
    shape.commit()


def _draw_warning(page: fitz.Page, x: float, y_center: float) -> None:
    """Draw a ⚠️ warning symbol at the given position."""
    page.insert_text(
        fitz.Point(x, y_center + _ICON_SIZE / 2 - 1),
        "\u26a0",  # ⚠ WARNING SIGN
        fontsize=_ICON_SIZE,
        fontfile=_SYMBOL_FONT,
        fontname="sym",
        color=_YELLOW,
    )


_ICON_DRAWERS = {
    "ok": _draw_checkmark,
    "mismatch": _draw_x_mark,
    "missing": _draw_x_mark,
    "unverified": _draw_warning,
}


# ---------------------------------------------------------------------------
# Main annotation logic
# ---------------------------------------------------------------------------


def _find_text_position(
    page: fitz.Page,
    search_text: str,
    used_positions: set[tuple[int, int]] | None = None,
    page_idx: int = 0,
) -> tuple[float, float] | None:
    """Search for *search_text* on *page* and return (x0, y_center) of the
    first match whose row hasn't been used yet, or ``None``.

    *used_positions* tracks ``(page_idx, round(y_center))`` keys already
    consumed so that duplicate descriptions land on different physical
    rows rather than stacking on the first occurrence.
    """
    if not search_text:
        return None
    if used_positions is None:
        used_positions = set()

    # Try searching for substrings of decreasing length (in case the full
    # description was truncated or reformatted).
    for length in (len(search_text), 60, 30):
        hits = page.search_for(search_text[:length])
        for r in hits:
            row_key = (page_idx, round((r.y0 + r.y1) / 2))
            if row_key not in used_positions:
                used_positions.add(row_key)
                return r.x0, (r.y0 + r.y1) / 2
    return None


def _determine_outcome(
    result: ValidationResult,
) -> Literal["APPROVED", "REJECTED", "INCONCLUSIVE"]:
    """Map a ValidationResult to an overall outcome for stamping."""
    if result.mismatches:
        return "REJECTED"
    if result.missing_items:
        return "INCONCLUSIVE"
    if result.status in ("no_pricing", "extraction_failed", "skipped"):
        return "INCONCLUSIVE"
    if any(a.status == "unverified" for a in result.annotations):
        return "INCONCLUSIVE"
    return "APPROVED"


def annotate_pdf(
    pdf_bytes: bytes,
    result: ValidationResult,
) -> tuple[bytes, str]:
    """
    Create a marked-up copy of a PO PDF.

    - Green ✓ next to verified line items.
    - Red ✗ next to price mismatches, with a comment showing the discrepancy.
    - Yellow ⚠ next to items that could not be verified.
    - Overall stamp (Approved/Rejected/Inconclusive) on the top-right
      of the first page.
    - Missing work items listed at the bottom of the last page.

    Returns (annotated_pdf_bytes, output_filename).
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    annotations = result.annotations

    # Track text positions already used so duplicate descriptions
    # land on successive occurrences rather than the same spot.
    used_positions: set[tuple[int, int]] = set()

    # ---- Per-line annotations ----
    for ann in annotations:
        page_idx = ann.page_number or 0
        if page_idx >= len(doc):
            page_idx = 0
        page = doc[page_idx]

        draw_fn = _ICON_DRAWERS.get(ann.status, _draw_warning)

        # Determine position: prefer bbox, fall back to text search
        if ann.bbox:
            x = ann.bbox[0] - _ICON_SIZE - _ICON_MARGIN
            y_center = (ann.bbox[1] + ann.bbox[3]) / 2
            # Mark this row as used so text-search fallbacks skip it
            used_positions.add((page_idx, round(y_center)))
            # Clamp to page
            if x < 2:
                x = ann.bbox[2] + _ICON_MARGIN
        elif ann.search_text:
            pos = _find_text_position(page, ann.search_text, used_positions, page_idx)
            if pos:
                x = pos[0] - _ICON_SIZE - _ICON_MARGIN
                y_center = pos[1]
                if x < 2:
                    x = pos[0] + _ICON_MARGIN
            else:
                logger.debug(
                    "Could not locate text %r on page %d", ann.search_text, page_idx
                )
                continue
        else:
            continue  # no position info at all

        draw_fn(page, x, y_center)

        # Add comment text for mismatches (with white background for legibility)
        if ann.comment and ann.status in ("mismatch", "missing"):
            comment_x = x + _ICON_SIZE + _ICON_MARGIN
            comment_y = y_center + _COMMENT_FONT_SIZE / 2
            # Measure text width so we can draw a background rectangle
            text_width = fitz.get_text_length(
                ann.comment, fontname="helv", fontsize=_COMMENT_FONT_SIZE
            )
            pad = 2  # padding around text
            bg_rect = fitz.Rect(
                comment_x - pad,
                comment_y - _COMMENT_FONT_SIZE - pad,
                comment_x + text_width + pad,
                comment_y + pad,
            )
            shape = page.new_shape()
            shape.draw_rect(bg_rect)
            shape.finish(color=None, fill=(1, 1, 1))  # white fill, no border
            shape.commit()
            page.insert_text(
                fitz.Point(comment_x, comment_y),
                ann.comment,
                fontsize=_COMMENT_FONT_SIZE,
                fontname="helv",
                color=_COMMENT_COLOR,
            )

    # ---- Missing work items summary at bottom of last page ----
    if result.missing_items:
        header_text = "MISSING WORK ITEMS (not found on PO):"
        header_fs = 9
        item_fs = 8
        line_spacing = 12  # vertical distance between lines

        # Build the text lines first (without y-coordinates)
        text_lines: list[tuple[str, float]] = []  # (text, fontsize)
        text_lines.append((header_text, header_fs))
        for mi in result.missing_items:
            price_str = (
                f"${mi.expected_price:,.2f}" if mi.expected_price is not None else "n/a"
            )
            text_lines.append(
                (
                    f"  S/N {mi.serial_number}  \u2014  {mi.asset_name}  ({price_str})",
                    item_fs,
                )
            )

        # Calculate total block height
        block_height = header_fs + line_spacing * (len(text_lines) - 1)
        bottom_margin = 20  # minimum gap from page bottom

        last_page = doc[-1]
        page_rect = last_page.rect
        available = page_rect.height - bottom_margin

        # Position the block so it fits on the page.  If the block is
        # taller than half the page, add a new blank page instead.
        if block_height + bottom_margin > available / 2:
            last_page = doc.new_page(width=page_rect.width, height=page_rect.height)
            page_rect = last_page.rect
        y_start = page_rect.height - bottom_margin - block_height

        # Assign y-coordinates
        lines: list[tuple[str, float, float]] = []
        y = y_start
        for text, fs in text_lines:
            lines.append((text, fs, y))
            y += line_spacing

        # Draw a white background behind the entire block
        max_width = max(
            fitz.get_text_length(t, fontname="helv", fontsize=fs) for t, fs, _ in lines
        )
        pad = 4
        bg_rect = fitz.Rect(
            36 - pad,
            lines[0][2] - header_fs - pad,
            36 + max_width + pad,
            lines[-1][2] + pad,
        )
        shape = last_page.new_shape()
        shape.draw_rect(bg_rect)
        shape.finish(color=None, fill=(1, 1, 1))
        shape.commit()

        # Now draw the text on top
        for text, fs, ty in lines:
            last_page.insert_text(
                fitz.Point(36 if fs == header_fs else 40, ty),
                text,
                fontsize=fs,
                fontname="helv",
                color=_RED,
            )

    # ---- Stamp on first page ----
    outcome = _determine_outcome(result)
    stamp_path = _STAMP_FILES.get(outcome)
    if stamp_path and stamp_path.exists():
        first_page = doc[0]
        page_rect = first_page.rect

        # Target stamp size: 150px wide, maintain aspect ratio
        stamp_doc = fitz.open(str(stamp_path))
        stamp_page = stamp_doc[0]
        stamp_rect = stamp_page.rect
        scale = 150 / stamp_rect.width if stamp_rect.width else 1
        stamp_w = stamp_rect.width * scale
        stamp_h = stamp_rect.height * scale
        stamp_doc.close()

        # Position: top-right corner with margin
        margin = 20
        x0 = page_rect.width - stamp_w - margin
        y0 = margin
        target_rect = fitz.Rect(x0, y0, x0 + stamp_w, y0 + stamp_h)

        first_page.insert_image(
            target_rect,
            filename=str(stamp_path),
            overlay=True,
        )

    # ---- Build output filename ----
    # Append the outcome suffix to the original document name.
    doc_name = result.document_name or "UNKNOWN.pdf"
    stem = Path(doc_name).stem
    filename = f"{stem}_{outcome}.pdf"

    # ---- Serialize ----
    out_bytes = doc.tobytes(deflate=True)
    doc.close()

    return out_bytes, filename
