"""
Deterministic Analytics Engine.

Computes:
  1. Revenue by hour-of-day (bucketed by UTC hour)
  2. Top medicines by quantity (distinct ranking)
  3. Top medicines by revenue (distinct ranking)

This layer NEVER calls an LLM. It is the ground truth.
All money is integer paise throughout.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from app.models import (
    VisitRecord,
    AnalyticsReport,
    HourlyRevenue,
    MedicineRank,
)


def _hour_label(hour: int) -> str:
    """Convert 24h integer to display label: 0→'12am', 9→'9am', 13→'1pm'."""
    if hour == 0:
        return "12am"
    elif hour < 12:
        return f"{hour}am"
    elif hour == 12:
        return "12pm"
    else:
        return f"{hour - 12}pm"


def compute_analytics(
    records: list[VisitRecord],
    clinic_id: str,
    date: str,
) -> AnalyticsReport:
    """
    Compute analytics from validated, non-refund visit records.

    Revenue by hour uses amount_paid_paise (actual collected) for non-refund rows.
    Medicine rankings use line_items data from non-refund rows.
    """
    # ── Revenue by hour ──────────────────────────────────────────────
    hour_revenue: dict[int, int] = defaultdict(int)
    # Track all hours that appear in the data
    min_hour = 23
    max_hour = 0

    # ── Medicine aggregation ─────────────────────────────────────────
    drug_qty: dict[str, int] = defaultdict(int)
    drug_revenue: dict[str, int] = defaultdict(int)

    for record in records:
        if record.is_refund:
            continue

        # Parse hour from timestamp
        try:
            ts = datetime.fromisoformat(record.timestamp.replace("Z", "+00:00"))
            hour = ts.hour
        except ValueError:
            continue

        hour_revenue[hour] += record.amount_paid_paise
        min_hour = min(min_hour, hour)
        max_hour = max(max_hour, hour)

        # Aggregate line items
        for item in record.line_items:
            drug_qty[item.drug_name] += item.qty
            drug_revenue[item.drug_name] += item.qty * item.unit_price_paise

    # ── Build hourly revenue list (fill gaps) ────────────────────────
    hourly: list[HourlyRevenue] = []
    if hour_revenue:
        for h in range(min_hour, max_hour + 1):
            hourly.append(HourlyRevenue(
                hour=h,
                label=_hour_label(h),
                revenue_paise=hour_revenue.get(h, 0),
            ))

    # Identify peak hour
    peak = None
    if hourly:
        peak = max(hourly, key=lambda x: x.revenue_paise)

    # ── Top medicines by quantity ────────────────────────────────────
    sorted_by_qty = sorted(drug_qty.items(), key=lambda x: x[1], reverse=True)
    top_qty: list[MedicineRank] = [
        MedicineRank(
            rank=i + 1,
            drug_name=name,
            quantity=qty,
            revenue_paise=drug_revenue.get(name, 0),
        )
        for i, (name, qty) in enumerate(sorted_by_qty)
    ]

    # ── Top medicines by revenue ─────────────────────────────────────
    sorted_by_rev = sorted(drug_revenue.items(), key=lambda x: x[1], reverse=True)
    top_rev: list[MedicineRank] = [
        MedicineRank(
            rank=i + 1,
            drug_name=name,
            quantity=drug_qty.get(name, 0),
            revenue_paise=rev,
        )
        for i, (name, rev) in enumerate(sorted_by_rev)
    ]

    return AnalyticsReport(
        clinic_id=clinic_id,
        date=date,
        revenue_by_hour=hourly,
        peak_hour=peak,
        top_medicines_by_qty=top_qty,
        top_medicines_by_revenue=top_rev,
    )
