"""
Row-level validation for billing log records.

Rejects malformed rows with specific, actionable errors — never a generic 500.
Returns (valid_records, validation_errors) so the pipeline can process
partial data while surfacing issues.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.models import VisitRecord, PaymentMode


REQUIRED_FIELDS = [
    "clinic_id", "visit_id", "timestamp", "doctor_id",
    "line_items", "payment_mode", "amount_paid_paise",
    "discount_paise", "is_refund",
]

VALID_PAYMENT_MODES = {m.value for m in PaymentMode}


def validate_billing_log(raw_records: list[dict[str, Any]]) -> tuple[list[VisitRecord], list[dict]]:
    """
    Validate a list of raw billing record dicts.

    Returns:
        (valid_records, validation_errors)
        Each error dict has: visit_id (if available), field, message
    """
    valid: list[VisitRecord] = []
    errors: list[dict] = []
    seen_visit_ids: set[str] = set()

    if not isinstance(raw_records, list):
        errors.append({
            "visit_id": None,
            "field": "root",
            "message": "Billing log must be a JSON array of visit records.",
        })
        return valid, errors

    for idx, raw in enumerate(raw_records):
        if not isinstance(raw, dict):
            errors.append({
                "visit_id": None,
                "field": f"record[{idx}]",
                "message": f"Record at index {idx} is not a JSON object.",
            })
            continue

        visit_id = raw.get("visit_id", f"<unknown at index {idx}>")
        
        # Check for duplicate visit_id
        is_duplicate = False
        if visit_id in seen_visit_ids:
            errors.append({
                "visit_id": visit_id,
                "field": "visit_id",
                "message": f"Duplicate visit_id '{visit_id}' found. Each visit_id must be unique within the log.",
            })
            is_duplicate = True
        else:
            if isinstance(visit_id, str) and not visit_id.startswith("<unknown"):
                seen_visit_ids.add(visit_id)
        
        record_errors = _validate_single_record(raw, visit_id, idx)

        if record_errors or is_duplicate:
            if record_errors:
                errors.extend(record_errors)
        else:
            try:
                record = VisitRecord(**raw)
                valid.append(record)
            except Exception as exc:
                errors.append({
                    "visit_id": visit_id,
                    "field": "parse",
                    "message": f"Failed to parse record: {exc}",
                })

    return valid, errors


def _validate_single_record(raw: dict, visit_id: str, idx: int) -> list[dict]:
    """Validate a single raw record dict and return a list of errors."""
    errs: list[dict] = []

    # ── Check required fields ────────────────────────────────────────
    for field in REQUIRED_FIELDS:
        if field not in raw:
            errs.append({
                "visit_id": visit_id,
                "field": field,
                "message": f"Missing required field '{field}'. "
                           f"Every billing record must include: {', '.join(REQUIRED_FIELDS)}.",
            })

    # Stop early if critical fields are missing
    if errs:
        return errs

    # ── Type checks ──────────────────────────────────────────────────
    if not isinstance(raw["clinic_id"], str) or not raw["clinic_id"]:
        errs.append({
            "visit_id": visit_id,
            "field": "clinic_id",
            "message": "clinic_id must be a non-empty string.",
        })

    if not isinstance(raw["visit_id"], str) or not raw["visit_id"]:
        errs.append({
            "visit_id": visit_id,
            "field": "visit_id",
            "message": "visit_id must be a non-empty string.",
        })

    # ── Timestamp ────────────────────────────────────────────────────
    ts = raw.get("timestamp")
    if not isinstance(ts, str):
        errs.append({
            "visit_id": visit_id,
            "field": "timestamp",
            "message": "timestamp must be an ISO 8601 string (e.g. '2026-07-27T09:10:00Z').",
        })
    else:
        try:
            datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            errs.append({
                "visit_id": visit_id,
                "field": "timestamp",
                "message": f"timestamp '{ts}' is not valid ISO 8601. "
                           f"Expected format: '2026-07-27T09:10:00Z'.",
            })

    # ── Payment mode ─────────────────────────────────────────────────
    pm = raw.get("payment_mode")
    if pm not in VALID_PAYMENT_MODES:
        errs.append({
            "visit_id": visit_id,
            "field": "payment_mode",
            "message": f"payment_mode '{pm}' is invalid. "
                       f"Must be one of: {', '.join(sorted(VALID_PAYMENT_MODES))}.",
        })

    # ── Monetary fields ──────────────────────────────────────────────
    if not isinstance(raw.get("amount_paid_paise"), int):
        errs.append({
            "visit_id": visit_id,
            "field": "amount_paid_paise",
            "message": "amount_paid_paise must be an integer (paise). "
                       "Do not use floats or strings.",
        })

    if not isinstance(raw.get("discount_paise"), int) or raw["discount_paise"] < 0:
        errs.append({
            "visit_id": visit_id,
            "field": "discount_paise",
            "message": "discount_paise must be a non-negative integer (paise).",
        })

    # ── Refund consistency ───────────────────────────────────────────
    is_refund = raw.get("is_refund")
    if not isinstance(is_refund, bool):
        errs.append({
            "visit_id": visit_id,
            "field": "is_refund",
            "message": "is_refund must be a boolean (true/false).",
        })
    elif is_refund and isinstance(raw.get("amount_paid_paise"), int):
        if raw["amount_paid_paise"] > 0:
            errs.append({
                "visit_id": visit_id,
                "field": "amount_paid_paise",
                "message": "Refund record has positive amount_paid_paise. "
                           "Refund amounts should be negative (money going back).",
            })

    # ── Line items ───────────────────────────────────────────────────
    line_items = raw.get("line_items")
    if not isinstance(line_items, list):
        errs.append({
            "visit_id": visit_id,
            "field": "line_items",
            "message": "line_items must be an array of {drug_name, qty, unit_price_paise}.",
        })
    elif len(line_items) == 0:
        errs.append({
            "visit_id": visit_id,
            "field": "line_items",
            "message": "line_items array is empty. Each visit must have at least one item.",
        })
    else:
        for li_idx, item in enumerate(line_items):
            if not isinstance(item, dict):
                errs.append({
                    "visit_id": visit_id,
                    "field": f"line_items[{li_idx}]",
                    "message": f"Line item at index {li_idx} is not a JSON object.",
                })
                continue
            if "drug_name" not in item or not isinstance(item.get("drug_name"), str):
                errs.append({
                    "visit_id": visit_id,
                    "field": f"line_items[{li_idx}].drug_name",
                    "message": "drug_name is required and must be a string.",
                })
            if "qty" not in item or not isinstance(item.get("qty"), int) or item["qty"] < 0:
                errs.append({
                    "visit_id": visit_id,
                    "field": f"line_items[{li_idx}].qty",
                    "message": "qty is required and must be a non-negative integer.",
                })
            if "unit_price_paise" not in item or not isinstance(item.get("unit_price_paise"), int) or item["unit_price_paise"] < 0:
                errs.append({
                    "visit_id": visit_id,
                    "field": f"line_items[{li_idx}].unit_price_paise",
                    "message": "unit_price_paise is required and must be a non-negative integer.",
                })

    return errs
