"""
Pydantic models for the SwasthiQ EOD Billing & Analytics Agent.

All monetary values are stored as integer paise throughout the system.
Conversion to rupees happens only at the API response / display layer.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ── Input Schema ─────────────────────────────────────────────────────

class PaymentMode(str, Enum):
    cash = "cash"
    card = "card"
    upi = "upi"


class LineItem(BaseModel):
    drug_name: str
    qty: int = Field(..., ge=0)
    unit_price_paise: int = Field(..., ge=0)


class VisitRecord(BaseModel):
    """A single visit/transaction from the billing log."""
    clinic_id: str
    visit_id: str
    timestamp: str  # ISO 8601 UTC
    doctor_id: str
    line_items: list[LineItem]
    payment_mode: PaymentMode
    amount_paid_paise: int
    discount_paise: int = Field(default=0, ge=0)
    is_refund: bool = False


# ── Reconciliation Output ────────────────────────────────────────────

class ModeBreakdown(BaseModel):
    """Billed / Collected / Outstanding for a single payment mode."""
    mode: str
    billed_paise: int = 0
    collected_paise: int = 0
    outstanding_paise: int = 0
    discount_paise: int = 0
    refunds_paise: int = 0


class ReconciliationReport(BaseModel):
    clinic_id: str
    date: str
    total_billed_paise: int = 0
    total_collected_paise: int = 0
    total_outstanding_paise: int = 0
    total_refunds_paise: int = 0
    total_discount_paise: int = 0
    visit_count: int = 0
    refund_count: int = 0
    pending_visit_count: int = 0
    mode_breakdown: list[ModeBreakdown] = []
    validation_errors: list[dict] = []


# ── Analytics Output ─────────────────────────────────────────────────

class HourlyRevenue(BaseModel):
    hour: int  # 0-23
    label: str  # e.g. "9am", "12pm"
    revenue_paise: int = 0


class MedicineRank(BaseModel):
    rank: int
    drug_name: str
    quantity: int = 0
    revenue_paise: int = 0


class AnalyticsReport(BaseModel):
    clinic_id: str
    date: str
    revenue_by_hour: list[HourlyRevenue] = []
    peak_hour: Optional[HourlyRevenue] = None
    top_medicines_by_qty: list[MedicineRank] = []
    top_medicines_by_revenue: list[MedicineRank] = []


# ── Narrative Output ─────────────────────────────────────────────────

class TracedFigure(BaseModel):
    """A single number from the narrative mapped back to its report field."""
    display_value: str  # e.g. "₹3,260"
    field_name: str  # e.g. "total_billed"


class NarrativeReport(BaseModel):
    clinic_id: str
    date: str
    narrative: str = ""
    traced_figures: list[TracedFigure] = []
    status: str = "success"  # "success" | "error"
    error_message: Optional[str] = None
