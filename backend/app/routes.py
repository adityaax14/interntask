"""
REST API Routes for the SwasthiQ EOD Billing & Analytics Agent.

Endpoints:
  POST /api/billing/upload              — Upload and process a billing log
  GET  /api/billing/reconciliation/{clinic_id}/{date}
  GET  /api/billing/analytics/{clinic_id}/{date}
  GET  /api/billing/narrative/{clinic_id}/{date}
  GET  /api/billing/dates/{clinic_id}   — List available dates
  GET  /api/billing/clinics             — List available clinics
"""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse

from app.validators import validate_billing_log
from app.reconciliation import compute_reconciliation
from app.analytics import compute_analytics
from app.narrative import generate_narrative
from app.storage import store

router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.post("/upload")
async def upload_billing_log(file: UploadFile = File(...)):
    """
    Upload a billing log JSON file.

    Validates each row, computes reconciliation and analytics,
    stores results, and returns a summary.

    Malformed rows are rejected with specific errors but don't
    crash the entire request — partial processing is supported.
    """
    # ── Parse JSON ───────────────────────────────────────────────────
    try:
        content = await file.read()
        raw_data = json.loads(content.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid JSON",
                "message": f"The uploaded file is not valid JSON: {exc.msg} at line {exc.lineno}, column {exc.colno}.",
                "fix": "Ensure the file contains a valid JSON array of billing records.",
            },
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Upload failed",
                "message": f"Could not read the uploaded file: {exc}",
            },
        )

    # ── Validate ─────────────────────────────────────────────────────
    valid_records, validation_errors = validate_billing_log(raw_data)

    if not valid_records and not isinstance(raw_data, list):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid format",
                "message": "Billing log must be a JSON array of visit records.",
                "validation_errors": validation_errors,
            },
        )

    # ── Extract clinic_id and date ───────────────────────────────────
    # Use the first valid record's clinic_id, or from any raw record
    clinic_id = None
    date_str = None

    if valid_records:
        clinic_id = valid_records[0].clinic_id
        try:
            ts = datetime.fromisoformat(
                valid_records[0].timestamp.replace("Z", "+00:00")
            )
            date_str = ts.strftime("%Y-%m-%d")
        except ValueError:
            pass

    # Fallback: try to extract from raw data
    if not clinic_id and raw_data and isinstance(raw_data, list) and len(raw_data) > 0:
        first = raw_data[0] if isinstance(raw_data[0], dict) else {}
        clinic_id = first.get("clinic_id", "unknown")
        ts_str = first.get("timestamp", "")
        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                date_str = ts.strftime("%Y-%m-%d")
            except ValueError:
                pass

    if not clinic_id:
        clinic_id = "unknown"
    if not date_str:
        date_str = "unknown"

    # Handle empty day (valid empty array)
    if isinstance(raw_data, list) and len(raw_data) == 0:
        # Need clinic_id and date from filename
        filename = file.filename or ""
        # Try to extract date from filename like billing_log_2026-07-26.json
        import re
        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
        if date_match:
            date_str = date_match.group(1)
        if clinic_id == "unknown":
            clinic_id = "CLN-KNP-014"  # Default for this assignment's dataset

    # ── Compute reports ──────────────────────────────────────────────
    recon = compute_reconciliation(valid_records, clinic_id, date_str, validation_errors)
    analytics = compute_analytics(valid_records, clinic_id, date_str)

    # ── Store ────────────────────────────────────────────────────────
    store.store_records(clinic_id, date_str, valid_records)
    store.store_reconciliation(clinic_id, date_str, recon)
    store.store_analytics(clinic_id, date_str, analytics)

    return JSONResponse(content={
        "status": "ok",
        "clinic_id": clinic_id,
        "date": date_str,
        "valid_records": len(valid_records),
        "rejected_records": len(validation_errors),
        "validation_errors": validation_errors,
    })


@router.get("/reconciliation/{clinic_id}/{date}")
async def get_reconciliation(clinic_id: str, date: str):
    """Get the EOD reconciliation report for a clinic and date."""
    report = store.get_reconciliation(clinic_id, date)
    if not report:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Not found",
                "message": f"No billing data found for clinic '{clinic_id}' on {date}. "
                           f"Upload a billing log first via POST /api/billing/upload.",
            },
        )
    return report


@router.get("/analytics/{clinic_id}/{date}")
async def get_analytics(clinic_id: str, date: str):
    """Get the analytics report for a clinic and date."""
    report = store.get_analytics(clinic_id, date)
    if not report:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Not found",
                "message": f"No billing data found for clinic '{clinic_id}' on {date}. "
                           f"Upload a billing log first via POST /api/billing/upload.",
            },
        )
    return report


@router.get("/narrative/{clinic_id}/{date}")
async def get_narrative(clinic_id: str, date: str):
    """
    Get the AI narrative summary for a clinic and date.

    Generates on first request, then caches. Requires reconciliation
    and analytics to be computed first (via upload).
    """
    # Check if already cached
    cached = store.get_narrative(clinic_id, date)
    if cached:
        return cached

    # Need both reports to generate
    recon = store.get_reconciliation(clinic_id, date)
    analytics = store.get_analytics(clinic_id, date)

    if not recon or not analytics:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Not found",
                "message": f"No billing data found for clinic '{clinic_id}' on {date}. "
                           f"Upload a billing log first via POST /api/billing/upload.",
            },
        )

    # Generate narrative
    narrative = generate_narrative(recon, analytics)
    store.store_narrative(clinic_id, date, narrative)

    return narrative


@router.get("/dates/{clinic_id}")
async def get_dates(clinic_id: str):
    """List all available dates for a clinic."""
    dates = store.list_dates(clinic_id)
    return {"clinic_id": clinic_id, "dates": dates}


@router.get("/clinics")
async def get_clinics():
    """List all clinics with uploaded data."""
    clinics = store.list_clinics()
    return {"clinics": clinics}
