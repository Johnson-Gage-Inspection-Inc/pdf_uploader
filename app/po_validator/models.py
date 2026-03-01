"""Pydantic models for PO extraction and validation results."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


@dataclass
class WorkItemData:
    """Normalized representation of a Qualer SDK work item.

    Wrapping SDK models with getattr() into this dataclass eliminates
    scattered defensive attribute access throughout the validation code.
    """

    work_item_id: int
    serial_number: str
    asset_name: str
    service_charge: float | None
    service_total: float | None

    @classmethod
    def from_sdk_model(cls, wi: object) -> "WorkItemData":
        return cls(
            work_item_id=getattr(wi, "work_item_id", 0) or 0,
            serial_number=getattr(wi, "serial_number", "") or "",
            asset_name=(
                getattr(wi, "asset_name", "")
                or getattr(wi, "asset_description", "")
                or ""
            ),
            service_charge=getattr(wi, "service_charge", None),
            service_total=getattr(wi, "service_total", None),
        )


@dataclass(order=True)
class PriceMatchCandidate:
    """A candidate price match between a work item and a PO line item.

    Sortable by price_diff (smallest difference first).
    """

    price_diff: float
    wi_idx: int
    po_idx: int
    expected_price: float
    po_price: float


class POLineItem(BaseModel):
    """A single line item extracted from a purchase order PDF."""

    serial_number: str | None = Field(
        None, description="Serial number / S/N of the instrument or tool"
    )
    description: str = Field("", description="Line item description text")
    unit_price: float | None = Field(
        None, description="Per-unit price listed on the PO"
    )
    quantity: int | None = Field(None, description="Quantity ordered")
    extended_price: float | None = Field(
        None, description="Extended (total) price for this line item"
    )
    page_number: int | None = Field(
        None, description="0-based page index where this item appears"
    )
    bbox: tuple[float, float, float, float] | None = Field(
        None, description="Bounding box (x0, top, x1, bottom) in PDF points"
    )


class POExtraction(BaseModel):
    """Structured data extracted from a PO PDF."""

    po_number: str = Field("", description="Purchase order number")
    line_items: list[POLineItem] = Field(default_factory=list)
    confidence: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="Confidence score for the extraction (0-1)",
    )
    extraction_method: Literal["table", "llm", "text", "none"] = "none"
    raw_text: str = Field("", description="Raw text extracted from PDF (for debugging)")


class PriceMismatch(BaseModel):
    """A mismatch between PO price and Qualer expected price for a work item."""

    serial_number: str
    po_price: float
    expected_price: float
    difference: float = Field(
        description="po_price - expected_price (positive = PO overcharged)"
    )
    description: str = ""
    work_item_id: int | None = None


class MissingWorkItem(BaseModel):
    """A Qualer work item that was not found on the PO."""

    work_item_id: int
    serial_number: str = ""
    asset_name: str = ""
    expected_price: float | None = None


class LineAnnotation(BaseModel):
    """Annotation to draw on a PO PDF for a single line item."""

    status: Literal["ok", "mismatch", "missing", "unverified"] = Field(
        description=(
            "ok = price verified, mismatch = price wrong, "
            "missing = work item not on PO, unverified = could not check"
        )
    )
    comment: str = Field("", description="Explanatory text for the annotation")
    page_number: int | None = Field(None, description="0-based page to annotate")
    bbox: tuple[float, float, float, float] | None = Field(
        None, description="Row bounding box for icon placement"
    )
    search_text: str = Field(
        "", description="Fallback text to search for if bbox is unavailable"
    )


class ValidationResult(BaseModel):
    """Result of validating a single PO PDF against Qualer work items."""

    document_name: str = ""
    po_number: str = ""
    service_order_id: int | None = None
    status: Literal["pass", "fail", "no_pricing", "extraction_failed", "skipped"] = (
        "extraction_failed"
    )
    mismatches: list[PriceMismatch] = Field(default_factory=list)
    missing_items: list[MissingWorkItem] = Field(default_factory=list)
    annotations: list[LineAnnotation] = Field(default_factory=list)
    po_line_items_total: int = 0
    line_items_checked: int = 0
    line_items_matched: int = 0
    work_items_total: int = 0
    extraction_method: Literal["table", "llm", "text", "none"] = "none"
    confidence: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.now)
    notes: str = ""

    def __repr__(self) -> str:
        return (
            f"<ValidationResult {self.document_name!r} "
            f"PO# {self.po_number!r} "
            f"status={self.status} "
            f"mismatches={len(self.mismatches)} "
            f"missing_items={len(self.missing_items)}>"
        )
