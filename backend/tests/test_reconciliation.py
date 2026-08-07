"""
Tests for the deterministic reconciliation and analytics layers.

Covers:
  - Happy path (July 27 data — full day with 18 valid + 1 malformed row)
  - All-refunds day (July 25 — only refund records)
  - Empty day (July 26 — zero transactions)
  - Malformed row rejection (missing field, invalid payment mode)
  - Paise precision (no floating point errors)
"""

import json
import pytest
from pathlib import Path

from app.validators import validate_billing_log
from app.reconciliation import compute_reconciliation
from app.analytics import compute_analytics


# ── Test Data Paths ──────────────────────────────────────────────────

SAMPLE_DIR = Path(__file__).parent.parent.parent / "sample_data"


def _load_sample(filename: str) -> list[dict]:
    path = SAMPLE_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════════════
# July 27 — Happy Path (main day with edge cases)
# ═══════════════════════════════════════════════════════════════════════

class TestJuly27HappyPath:
    """Full day: 19 raw records, 18 valid, 1 rejected (V-019 missing payment_mode)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        raw = _load_sample("billing_log_2026-07-27.json")
        self.valid, self.errors = validate_billing_log(raw)
        self.recon = compute_reconciliation(
            self.valid, "CLN-KNP-014", "2026-07-27", self.errors
        )
        self.analytics = compute_analytics(
            self.valid, "CLN-KNP-014", "2026-07-27"
        )

    def test_validation_rejects_missing_payment_mode(self):
        """V-20260727-019 is missing payment_mode — should be rejected."""
        assert len(self.errors) > 0
        rejected_ids = [e.get("visit_id") for e in self.errors]
        assert "V-20260727-019" in rejected_ids

    def test_valid_record_count(self):
        """18 of 19 records should pass validation."""
        assert len(self.valid) == 18

    def test_visit_count(self):
        """All 18 valid records are non-refund, so visit_count = 18."""
        assert self.recon.visit_count == 18

    def test_refund_count_zero(self):
        """No refunds on July 27."""
        assert self.recon.refund_count == 0
        assert self.recon.total_refunds_paise == 0

    def test_total_billed_paise(self):
        """
        Total billed = sum of (qty × unit_price_paise) for all 18 non-refund rows.
        Hand-computed: 326,000 paise = ₹3,260.00
        """
        assert self.recon.total_billed_paise == 326000

    def test_total_collected_paise(self):
        """
        Total collected = sum of amount_paid_paise for 18 non-refund rows.
        Hand-computed: 317,200 paise = ₹3,172.00
        """
        assert self.recon.total_collected_paise == 317200

    def test_total_outstanding_paise(self):
        """
        Outstanding = (billed - discounts) - collected
        = (326000 - 7000) - 317200 = 1800 paise = ₹18.00
        """
        assert self.recon.total_outstanding_paise == 1800

    def test_total_discount_paise(self):
        """Total discounts across all rows = 7000 paise."""
        assert self.recon.total_discount_paise == 7000

    def test_pending_visits(self):
        """3 visits have outstanding balance: V-004, V-011, V-016."""
        assert self.recon.pending_visit_count == 3

    def test_mode_breakdown_cash(self):
        """Cash: billed=129000, collected=127000, outstanding=500."""
        cash = next(m for m in self.recon.mode_breakdown if m.mode == "cash")
        assert cash.billed_paise == 129000
        assert cash.collected_paise == 127000
        assert cash.outstanding_paise == 500

    def test_mode_breakdown_card(self):
        """Card: billed=87000, collected=82700, outstanding=800."""
        card = next(m for m in self.recon.mode_breakdown if m.mode == "card")
        assert card.billed_paise == 87000
        assert card.collected_paise == 82700
        assert card.outstanding_paise == 800

    def test_mode_breakdown_upi(self):
        """UPI: billed=110000, collected=107500, outstanding=500."""
        upi = next(m for m in self.recon.mode_breakdown if m.mode == "upi")
        assert upi.billed_paise == 110000
        assert upi.collected_paise == 107500
        assert upi.outstanding_paise == 500

    def test_analytics_peak_hour(self):
        """Peak hour should be 1pm (13:xx) with revenue 75,500 paise."""
        assert self.analytics.peak_hour is not None
        assert self.analytics.peak_hour.hour == 13
        assert self.analytics.peak_hour.revenue_paise == 75500

    def test_analytics_revenue_by_hour_coverage(self):
        """Should have hourly data from 9am to 6pm."""
        hours = [h.hour for h in self.analytics.revenue_by_hour]
        assert min(hours) == 9
        assert max(hours) == 18

    def test_top_medicine_by_qty(self):
        """OMEPRAZOLE should be #1 by quantity with 18 units."""
        top = self.analytics.top_medicines_by_qty[0]
        assert top.drug_name == "OMEPRAZOLE"
        assert top.quantity == 18

    def test_top_medicine_by_revenue(self):
        """ATORVASTATIN should be #1 by revenue with 120,000 paise."""
        top = self.analytics.top_medicines_by_revenue[0]
        assert top.drug_name == "ATORVASTATIN"
        assert top.revenue_paise == 120000

    def test_misspelled_drug_treated_as_separate(self):
        """PARACETMOL (typo) is treated as a distinct drug from PARACETAMOL."""
        drug_names = [m.drug_name for m in self.analytics.top_medicines_by_qty]
        assert "PARACETAMOL" in drug_names
        assert "PARACETMOL" in drug_names

    def test_all_money_is_integer(self):
        """Every monetary value must be an integer (paise), not float."""
        assert isinstance(self.recon.total_billed_paise, int)
        assert isinstance(self.recon.total_collected_paise, int)
        assert isinstance(self.recon.total_outstanding_paise, int)
        assert isinstance(self.recon.total_refunds_paise, int)
        for m in self.recon.mode_breakdown:
            assert isinstance(m.billed_paise, int)
            assert isinstance(m.collected_paise, int)
            assert isinstance(m.outstanding_paise, int)


# ═══════════════════════════════════════════════════════════════════════
# July 25 — All Refunds Day (non-happy path)
# ═══════════════════════════════════════════════════════════════════════

class TestJuly25AllRefunds:
    """Every record is a refund. No positive revenue at all."""

    @pytest.fixture(autouse=True)
    def setup(self):
        raw = _load_sample("billing_log_2026-07-25.json")
        self.valid, self.errors = validate_billing_log(raw)
        self.recon = compute_reconciliation(
            self.valid, "CLN-KNP-014", "2026-07-25", self.errors
        )
        self.analytics = compute_analytics(
            self.valid, "CLN-KNP-014", "2026-07-25"
        )

    def test_all_records_valid(self):
        assert len(self.valid) == 3
        assert len(self.errors) == 0

    def test_zero_billed(self):
        assert self.recon.total_billed_paise == -49000

    def test_zero_collected(self):
        assert self.recon.total_collected_paise == -49000

    def test_zero_outstanding(self):
        assert self.recon.total_outstanding_paise == 0

    def test_total_refunds(self):
        """3 refunds: 24000 + 22000 + 3000 = 49000 paise."""
        assert self.recon.total_refunds_paise == 49000

    def test_refund_count(self):
        assert self.recon.refund_count == 3

    def test_visit_count_zero(self):
        """No non-refund visits."""
        assert self.recon.visit_count == 0

    def test_no_peak_hour(self):
        """No non-refund revenue, so no peak hour."""
        assert self.analytics.peak_hour is None

    def test_no_medicine_rankings(self):
        """Refund rows shouldn't appear in top medicines."""
        assert len(self.analytics.top_medicines_by_qty) == 0
        assert len(self.analytics.top_medicines_by_revenue) == 0


# ═══════════════════════════════════════════════════════════════════════
# July 26 — Empty Day
# ═══════════════════════════════════════════════════════════════════════

class TestJuly26EmptyDay:
    """Empty JSON array — zero transactions."""

    @pytest.fixture(autouse=True)
    def setup(self):
        raw = _load_sample("billing_log_2026-07-26.json")
        self.valid, self.errors = validate_billing_log(raw)
        self.recon = compute_reconciliation(
            self.valid, "CLN-KNP-014", "2026-07-26", self.errors
        )
        self.analytics = compute_analytics(
            self.valid, "CLN-KNP-014", "2026-07-26"
        )

    def test_no_records(self):
        assert len(self.valid) == 0
        assert len(self.errors) == 0

    def test_all_zeros(self):
        assert self.recon.total_billed_paise == 0
        assert self.recon.total_collected_paise == 0
        assert self.recon.total_outstanding_paise == 0
        assert self.recon.total_refunds_paise == 0
        assert self.recon.visit_count == 0
        assert self.recon.refund_count == 0

    def test_empty_analytics(self):
        assert len(self.analytics.revenue_by_hour) == 0
        assert self.analytics.peak_hour is None
        assert len(self.analytics.top_medicines_by_qty) == 0


# ═══════════════════════════════════════════════════════════════════════
# Malformed Row Rejection
# ═══════════════════════════════════════════════════════════════════════

class TestMalformedRows:
    """Unit tests for the validator on intentionally bad data."""

    def test_not_a_list(self):
        valid, errors = validate_billing_log({"foo": "bar"})
        assert len(valid) == 0
        assert len(errors) == 1
        assert "JSON array" in errors[0]["message"]

    def test_missing_required_field(self):
        """A record missing payment_mode should produce a specific error."""
        record = {
            "clinic_id": "CLN-TEST",
            "visit_id": "V-TEST-001",
            "timestamp": "2026-07-27T09:00:00Z",
            "doctor_id": "DOC-001",
            "line_items": [{"drug_name": "TEST", "qty": 1, "unit_price_paise": 1000}],
            # payment_mode intentionally omitted
            "amount_paid_paise": 1000,
            "discount_paise": 0,
            "is_refund": False,
        }
        valid, errors = validate_billing_log([record])
        assert len(valid) == 0
        assert any("payment_mode" in e.get("field", "") for e in errors)

    def test_invalid_payment_mode(self):
        record = {
            "clinic_id": "CLN-TEST",
            "visit_id": "V-TEST-001",
            "timestamp": "2026-07-27T09:00:00Z",
            "doctor_id": "DOC-001",
            "line_items": [{"drug_name": "TEST", "qty": 1, "unit_price_paise": 1000}],
            "payment_mode": "bitcoin",
            "amount_paid_paise": 1000,
            "discount_paise": 0,
            "is_refund": False,
        }
        valid, errors = validate_billing_log([record])
        assert len(valid) == 0
        assert any("bitcoin" in e.get("message", "") for e in errors)

    def test_refund_with_positive_amount(self):
        record = {
            "clinic_id": "CLN-TEST",
            "visit_id": "V-TEST-001",
            "timestamp": "2026-07-27T09:00:00Z",
            "doctor_id": "DOC-001",
            "line_items": [{"drug_name": "TEST", "qty": 1, "unit_price_paise": 1000}],
            "payment_mode": "cash",
            "amount_paid_paise": 1000,  # Should be negative for refund
            "discount_paise": 0,
            "is_refund": True,
        }
        valid, errors = validate_billing_log([record])
        assert len(valid) == 0
        assert any("negative" in e.get("message", "").lower() or "refund" in e.get("message", "").lower() for e in errors)

    def test_invalid_timestamp(self):
        record = {
            "clinic_id": "CLN-TEST",
            "visit_id": "V-TEST-001",
            "timestamp": "not-a-date",
            "doctor_id": "DOC-001",
            "line_items": [{"drug_name": "TEST", "qty": 1, "unit_price_paise": 1000}],
            "payment_mode": "cash",
            "amount_paid_paise": 1000,
            "discount_paise": 0,
            "is_refund": False,
        }
        valid, errors = validate_billing_log([record])
        assert len(valid) == 0
        assert any("timestamp" in e.get("field", "") for e in errors)

    def test_record_not_dict(self):
        valid, errors = validate_billing_log(["string_not_dict"])
        assert len(valid) == 0
        assert len(errors) == 1

    def test_paise_precision_no_float(self):
        """Ensure amounts stay as integers, no float conversion."""
        record = {
            "clinic_id": "CLN-TEST",
            "visit_id": "V-TEST-001",
            "timestamp": "2026-07-27T09:00:00Z",
            "doctor_id": "DOC-001",
            "line_items": [{"drug_name": "TEST", "qty": 3, "unit_price_paise": 3333}],
            "payment_mode": "cash",
            "amount_paid_paise": 9999,
            "discount_paise": 0,
            "is_refund": False,
        }
        valid, errors = validate_billing_log([record])
        assert len(valid) == 1
        assert len(errors) == 0

        recon = compute_reconciliation(valid, "CLN-TEST", "2026-07-27")
        assert recon.total_billed_paise == 9999  # 3 × 3333
        assert isinstance(recon.total_billed_paise, int)
        assert recon.total_collected_paise == 9999
        assert isinstance(recon.total_collected_paise, int)
