"""
LLM Narrative Generator — Agentic Layer.

Given the deterministic reconciliation and analytics reports as input,
generates a short, owner-facing summary in WhatsApp-appropriate tone.

Every figure in the narrative is traced back to the report.
Handles malformed or off-schema model responses gracefully.

Uses Groq API (OpenAI-compatible) with Llama 3.3 70B.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from openai import OpenAI

from app.models import (
    ReconciliationReport,
    AnalyticsReport,
    NarrativeReport,
    TracedFigure,
)


def _paise_to_rupees_str(paise: int) -> str:
    """Convert paise to formatted rupee string: 326000 → '₹3,260'."""
    rupees = paise / 100
    if rupees == int(rupees):
        return f"₹{int(rupees):,}"
    return f"₹{rupees:,.2f}"


def _build_report_context(
    recon: ReconciliationReport,
    analytics: AnalyticsReport,
) -> dict[str, Any]:
    """Build a flat dict of facts the LLM is allowed to cite."""
    facts: dict[str, Any] = {
        "total_billed": _paise_to_rupees_str(recon.total_billed_paise),
        "total_collected": _paise_to_rupees_str(recon.total_collected_paise),
        "outstanding": _paise_to_rupees_str(recon.total_outstanding_paise),
        "refunds": _paise_to_rupees_str(recon.total_refunds_paise),
        "total_discount": _paise_to_rupees_str(recon.total_discount_paise),
        "visit_count": recon.visit_count,
        "refund_count": recon.refund_count,
        "pending_visit_count": recon.pending_visit_count,
    }

    if recon.total_billed_paise > 0:
        pct = round(recon.total_collected_paise / (recon.total_billed_paise - recon.total_discount_paise) * 100)
        facts["collection_pct"] = f"{pct}%"

    if analytics.peak_hour:
        facts["peak_hour"] = analytics.peak_hour.label
        facts["peak_hour_range"] = f"{analytics.peak_hour.label}–{_hour_label_next(analytics.peak_hour.hour)}"
        facts["peak_hour_revenue"] = _paise_to_rupees_str(analytics.peak_hour.revenue_paise)

    if analytics.top_medicines_by_qty:
        top = analytics.top_medicines_by_qty[0]
        facts["top_drug_by_qty"] = top.drug_name
        facts["top_drug_by_qty_count"] = top.quantity

    if analytics.top_medicines_by_revenue:
        top = analytics.top_medicines_by_revenue[0]
        facts["top_drug_by_revenue"] = top.drug_name
        facts["top_drug_by_revenue_amount"] = _paise_to_rupees_str(top.revenue_paise)

    return facts


def _hour_label_next(hour: int) -> str:
    """Next hour label for range display."""
    next_h = (hour + 1) % 24
    if next_h == 0:
        return "12am"
    elif next_h < 12:
        return f"{next_h}am"
    elif next_h == 12:
        return "12pm"
    else:
        return f"{next_h - 12}pm"


SYSTEM_PROMPT = """You are a clinic billing assistant. Generate a short WhatsApp-style end-of-day summary for the clinic owner.

RULES:
1. Use ONLY the numbers provided in the FACTS section below. Do NOT invent, estimate, or approximate any number.
2. Every figure you mention MUST come directly from the facts. If a metric isn't in the facts (like profit or cost), explicitly say it's not available — do NOT approximate.
3. Keep it concise — 4-6 short paragraphs max.
4. Friendly, professional WhatsApp tone. Use ₹ for currency.
5. Start with a greeting and date reference.

After the narrative, output a JSON block with traced figures — mapping each number you used to its field name from the facts.

Format your response EXACTLY as:
---NARRATIVE---
<your narrative text>
---TRACED---
[{"display_value": "₹X,XXX", "field_name": "total_billed"}, ...]
---END---
"""


def generate_narrative(
    recon: ReconciliationReport,
    analytics: AnalyticsReport,
) -> NarrativeReport:
    """
    Generate an LLM narrative summary grounded in the deterministic reports.

    Returns NarrativeReport with the narrative text, traced figures, and status.
    Handles malformed LLM responses gracefully — returns error status, not crash.
    """
    api_key = os.getenv("GROQ_API_KEY", "")
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    if not api_key:
        return NarrativeReport(
            clinic_id=recon.clinic_id,
            date=recon.date,
            narrative="",
            traced_figures=[],
            status="error",
            error_message="GROQ_API_KEY not configured. Set it in .env to enable AI summaries.",
        )

    # Build facts context
    facts = _build_report_context(recon, analytics)

    user_prompt = f"""Generate the end-of-day summary for this clinic.

FACTS (use ONLY these numbers):
{json.dumps(facts, indent=2)}

Clinic: {recon.clinic_id}
Date: {recon.date}
"""

    try:
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
        )

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=1024,
        )

        raw_output = response.choices[0].message.content or ""

        # Parse the structured response
        narrative, traced = _parse_llm_response(raw_output, facts)

        return NarrativeReport(
            clinic_id=recon.clinic_id,
            date=recon.date,
            narrative=narrative,
            traced_figures=traced,
            status="success",
        )

    except Exception as exc:
        return NarrativeReport(
            clinic_id=recon.clinic_id,
            date=recon.date,
            narrative="",
            traced_figures=[],
            status="error",
            error_message=f"LLM request failed: {type(exc).__name__}: {exc}",
        )


def _parse_llm_response(
    raw: str,
    facts: dict[str, Any],
) -> tuple[str, list[TracedFigure]]:
    """
    Parse the LLM's structured response into narrative + traced figures.

    Handles malformed responses by falling back to raw text with
    auto-extracted traced figures.
    """
    narrative = ""
    traced: list[TracedFigure] = []

    # Try to parse structured format
    if "---NARRATIVE---" in raw and "---TRACED---" in raw:
        parts = raw.split("---NARRATIVE---")
        if len(parts) > 1:
            rest = parts[1]
            if "---TRACED---" in rest:
                narr_part, traced_part = rest.split("---TRACED---", 1)
                narrative = narr_part.strip()

                # Extract JSON from traced part
                traced_part = traced_part.replace("---END---", "").strip()
                try:
                    traced_data = json.loads(traced_part)
                    if isinstance(traced_data, list):
                        for item in traced_data:
                            if isinstance(item, dict) and "display_value" in item and "field_name" in item:
                                fname = str(item["field_name"])
                                if fname in facts:
                                    traced.append(TracedFigure(
                                        display_value=str(item["display_value"]),
                                        field_name=fname,
                                    ))
                except json.JSONDecodeError:
                    pass

    # Fallback: use raw text as narrative
    if not narrative:
        # Clean up any format markers
        narrative = raw
        for marker in ["---NARRATIVE---", "---TRACED---", "---END---"]:
            narrative = narrative.replace(marker, "")
        narrative = narrative.strip()

    # If no traced figures from LLM, auto-extract from facts
    if not traced:
        traced = _auto_trace_figures(narrative, facts)

    return narrative, traced


def _auto_trace_figures(narrative: str, facts: dict[str, Any]) -> list[TracedFigure]:
    """
    Auto-extract traced figures by finding fact values mentioned in the narrative.
    This is the fallback when the LLM doesn't provide proper tracing.
    """
    traced: list[TracedFigure] = []
    seen = set()

    for field_name, value in facts.items():
        str_value = str(value)
        if str_value in narrative and field_name not in seen:
            traced.append(TracedFigure(
                display_value=str_value,
                field_name=field_name,
            ))
            seen.add(field_name)

    return traced
