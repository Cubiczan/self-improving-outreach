"""Lead queues: ClickHouse status=queued, or a local JSON file in mock mode."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from self_improving_outreach.models import Lead, LeadStatus
from self_improving_outreach.paths import sample_queue_path
from self_improving_outreach.stores.base import OutreachStore


def lead_from_mapping(data: dict[str, Any]) -> Lead:
    payload = dict(data)
    if "status" in payload and not isinstance(payload["status"], LeadStatus):
        payload["status"] = LeadStatus(payload["status"])
    return Lead.model_validate(payload)


def load_json_leads(path: str | Path) -> list[Lead]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    items = raw["leads"] if isinstance(raw, dict) and "leads" in raw else raw
    return [lead_from_mapping(item) for item in items]


def mappings_from_json_payload(data: Any) -> list[dict[str, Any]]:
    """Accept a lead object, a list, or `{leads: [...]}`."""
    if isinstance(data, dict) and "leads" in data:
        items = data["leads"]
    elif isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = [data]
    else:
        raise TypeError("JSON must be a lead object, a list, or {\"leads\": [...]}")
    return [dict(item) for item in items]


def upsert_leads_from_mappings(
    store: OutreachStore,
    items: list[dict[str, Any]],
    *,
    status: LeadStatus = LeadStatus.QUEUED,
) -> list[Lead]:
    upserted: list[Lead] = []
    for item in items:
        lead = lead_from_mapping(item)
        lead.status = status
        store.upsert_lead(lead)
        upserted.append(store.get_lead(lead.lead_id) or lead)
    return upserted


def _sample_leads(sample_path: str | Path | None = None) -> list[Lead]:
    path = Path(sample_path) if sample_path else sample_queue_path()
    if not path.exists():
        return []
    return load_json_leads(path)


def resolve_lead_from_sample(
    store: OutreachStore,
    lead_id: str,
    *,
    sample_path: str | Path | None = None,
) -> Optional[Lead]:
    lead = store.get_lead(lead_id)
    if lead is not None:
        return lead
    for queued in _sample_leads(sample_path):
        if queued.lead_id == lead_id:
            store.upsert_lead(queued)
            return store.get_lead(lead_id) or queued
    return None


def requeue_leads(
    store: OutreachStore,
    *,
    lead_ids: Optional[list[str]] = None,
    company: Optional[str] = None,
    all_sample: bool = False,
    clear_processing: bool = False,
    sample_path: str | Path | None = None,
) -> list[Lead]:
    """Set matching leads back to queued. Sample file is never overwritten."""
    if not any((lead_ids, company, all_sample, clear_processing)):
        raise ValueError(
            "Provide --lead-id, --company, --all-sample, and/or --clear-processing"
        )
    requeued: dict[str, Lead] = {}

    def _mark(lead: Lead) -> None:
        store.set_lead_status(lead.lead_id, LeadStatus.QUEUED)
        current = store.get_lead(lead.lead_id) or lead
        current.status = LeadStatus.QUEUED
        requeued[current.lead_id] = current

    if all_sample:
        samples = _sample_leads(sample_path)
        if not samples:
            raise FileNotFoundError("Sample lead queue not found")
        for lead in samples:
            lead.status = LeadStatus.QUEUED
            store.upsert_lead(lead)
            _mark(lead)

    for lead_id in lead_ids or []:
        lead = resolve_lead_from_sample(store, lead_id, sample_path=sample_path)
        if lead is None:
            raise KeyError(f"Unknown lead_id {lead_id}")
        _mark(lead)

    if company:
        needle = company.strip().lower()
        matches = [
            lead
            for lead in store.list_leads(limit=10_000)
            if needle in lead.company.lower()
        ]
        if not matches:
            for lead in _sample_leads(sample_path):
                if needle in lead.company.lower():
                    store.upsert_lead(lead)
                    matches.append(store.get_lead(lead.lead_id) or lead)
        if not matches:
            raise KeyError(f"No leads matching company {company!r}")
        for lead in matches:
            _mark(lead)

    if clear_processing:
        for lead in store.list_leads(status=LeadStatus.PROCESSING, limit=10_000):
            _mark(lead)

    return list(requeued.values())


class StoreLeadQueue:
    def __init__(self, store: OutreachStore) -> None:
        self.store = store

    def seed(self, leads: list[Lead]) -> None:
        for lead in leads:
            existing = self.store.get_lead(lead.lead_id)
            if existing is None:
                self.store.upsert_lead(lead)

    def claim(self, limit: int) -> list[Lead]:
        queued = self.store.list_leads(status=LeadStatus.QUEUED, limit=limit)
        claimed = []
        for lead in queued:
            self.store.set_lead_status(lead.lead_id, LeadStatus.PROCESSING)
            claimed.append(self.store.get_lead(lead.lead_id) or lead)
        return claimed

    def pending_count(self) -> int:
        return len(self.store.list_leads(status=LeadStatus.QUEUED, limit=10_000))


class JsonLeadQueue(StoreLeadQueue):
    """File-backed queue. Never overwrite the committed sample file."""

    def __init__(self, store: OutreachStore, path: str | Path, persist: bool | None = None) -> None:
        super().__init__(store)
        self.path = Path(path)
        self._persist = self.path.name != "leads.sample.json" if persist is None else persist
        if self.path.exists():
            self.seed(load_json_leads(self.path))

    def persist(self) -> None:
        if not self._persist:
            return
        leads = [lead.model_dump(mode="json") for lead in self.store.list_leads(limit=10_000)]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"leads": leads}, indent=2), encoding="utf-8")
