"""
Deterministic EOD Reconciliation Engine.

Computes: total billed, total collected, outstanding, and refunds —
each split by payment mode (cash / card / upi).

This layer NEVER calls an LLM. It is the ground truth.
All money is integer paise throughout.
"""

from __future__ import annotations

from collections import defaultdict

from app.models import VisitRecord, ReconciliationReport, ModeBreakdown


def compute_reconciliation(
    records: list[VisitRecord],
    clinic_id: str,
    date: str,
    validation_errors: list[dict] | None = None,
) -> ReconciliationReport:
    """
    Compute the end-of-day reconciliation from validated visit records.

    Total Billed   = sum(qty × unit_price_paise) for non-refund rows
    Total Collected = sum(amount_paid_paise) for non-refund rows
    Outstanding    = (Total Billed − Total Discounts) − Total Collected
    Refunds        = sum(|amount_paid_paise|) for refund rows

    Each metric is also broken down by payment_mode.
    """
    # Per-mode accumulators
    mode_billed: dict[str, int] = defaultdict(int)
    mode_collected: dict[str, int] = defaultdict(int)
    mode_discount: dict[str, int] = defaultdict(int)
    mode_refunds: dict[str, int] = defaultdict(int)

    visit_count = 0
    refund_count = 0
    pending_visits = 0

    for record in records:
        mode = record.payment_mode.value

        # Billed = gross value of line items
        row_billed = sum(
            item.qty * item.unit_price_paise for item in record.line_items
        )

        if record.is_refund:
            # Refunds are tracked separately and do not affect gross billed or collected
            mode_refunds[mode] += abs(record.amount_paid_paise)
            refund_count += 1
        else:
            # Normal transaction
            visit_count += 1
            discount = record.discount_paise

            mode_billed[mode] += row_billed
            mode_collected[mode] += record.amount_paid_paise
            mode_discount[mode] += discount

            # A visit is "pending" if there's outstanding balance
            row_outstanding = row_billed - discount - record.amount_paid_paise
            if row_outstanding > 0:
                pending_visits += 1

    # Aggregate totals
    total_billed = sum(mode_billed.values())
    total_collected = sum(mode_collected.values())
    total_discount = sum(mode_discount.values())
    total_refunds = sum(mode_refunds.values())
    total_outstanding = total_billed - total_discount - total_collected

    # Build mode breakdown (always include all three modes)
    breakdown: list[ModeBreakdown] = []
    for mode_key in ["cash", "card", "upi"]:
        b = mode_billed.get(mode_key, 0)
        c = mode_collected.get(mode_key, 0)
        d = mode_discount.get(mode_key, 0)
        r = mode_refunds.get(mode_key, 0)
        breakdown.append(ModeBreakdown(
            mode=mode_key,
            billed_paise=b,
            collected_paise=c,
            outstanding_paise=max(0, b - d - c),
            discount_paise=d,
            refunds_paise=r,
        ))

    return ReconciliationReport(
        clinic_id=clinic_id,
        date=date,
        total_billed_paise=total_billed,
        total_collected_paise=total_collected,
        total_outstanding_paise=max(0, total_outstanding),
        total_refunds_paise=total_refunds,
        total_discount_paise=total_discount,
        visit_count=visit_count,
        refund_count=refund_count,
        pending_visit_count=pending_visits,
        mode_breakdown=breakdown,
        validation_errors=validation_errors or [],
    )
