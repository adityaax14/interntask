"""
In-memory storage for billing data and computed reports.

Uses a simple dict keyed by (clinic_id, date).
SQLite or a full DB is not required per assignment constraints.
"""

from __future__ import annotations

from app.models import (
    VisitRecord,
    ReconciliationReport,
    AnalyticsReport,
    NarrativeReport,
)


class BillingStore:
    """Thread-safe (GIL) in-memory store for billing data and reports."""

    def __init__(self):
        # Raw validated records: (clinic_id, date) → list[VisitRecord]
        self._records: dict[tuple[str, str], list[VisitRecord]] = {}
        # Computed reports cache
        self._reconciliation: dict[tuple[str, str], ReconciliationReport] = {}
        self._analytics: dict[tuple[str, str], AnalyticsReport] = {}
        self._narrative: dict[tuple[str, str], NarrativeReport] = {}

    def _key(self, clinic_id: str, date: str) -> tuple[str, str]:
        return (clinic_id, date)

    # ── Records ──────────────────────────────────────────────────────

    def store_records(self, clinic_id: str, date: str, records: list[VisitRecord]):
        self._records[self._key(clinic_id, date)] = records

    def get_records(self, clinic_id: str, date: str) -> list[VisitRecord] | None:
        return self._records.get(self._key(clinic_id, date))

    # ── Reconciliation ───────────────────────────────────────────────

    def store_reconciliation(self, clinic_id: str, date: str, report: ReconciliationReport):
        self._reconciliation[self._key(clinic_id, date)] = report

    def get_reconciliation(self, clinic_id: str, date: str) -> ReconciliationReport | None:
        return self._reconciliation.get(self._key(clinic_id, date))

    # ── Analytics ────────────────────────────────────────────────────

    def store_analytics(self, clinic_id: str, date: str, report: AnalyticsReport):
        self._analytics[self._key(clinic_id, date)] = report

    def get_analytics(self, clinic_id: str, date: str) -> AnalyticsReport | None:
        return self._analytics.get(self._key(clinic_id, date))

    # ── Narrative ────────────────────────────────────────────────────

    def store_narrative(self, clinic_id: str, date: str, report: NarrativeReport):
        self._narrative[self._key(clinic_id, date)] = report

    def get_narrative(self, clinic_id: str, date: str) -> NarrativeReport | None:
        return self._narrative.get(self._key(clinic_id, date))

    # ── Query ────────────────────────────────────────────────────────

    def list_dates(self, clinic_id: str) -> list[str]:
        """Return sorted list of dates with uploaded data for a clinic."""
        dates = sorted(set(
            date for (cid, date) in self._records if cid == clinic_id
        ))
        return dates

    def list_clinics(self) -> list[str]:
        """Return sorted list of clinic IDs with uploaded data."""
        return sorted(set(cid for (cid, _) in self._records))


# Global singleton
store = BillingStore()
