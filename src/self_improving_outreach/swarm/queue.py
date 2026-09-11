"""Lead queues: ClickHouse status=queued, or a local JSON file in mock mode."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from self_improving_outreach.models import Lead, LeadStatus
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
