"""Thread-safe in-memory store used when ClickHouse is unavailable (CI / mock)."""

from __future__ import annotations

from copy import deepcopy
from threading import RLock
from typing import Optional

from self_improving_outreach.learning.defaults import default_patterns, default_weights
from self_improving_outreach.models import (
    AgentRun,
    IcpWeight,
    Lead,
    LeadStatus,
    MessagePattern,
    OutreachEvent,
    ToolFailure,
    utcnow,
)


class MemoryStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self.leads: dict[str, Lead] = {}
        self.events: list[OutreachEvent] = []
        self.patterns: dict[str, MessagePattern] = {
            p.pattern_id: p for p in default_patterns()
        }
        self.weights: dict[str, float] = dict(default_weights())
        self.weight_version = 1
        self.failures: list[ToolFailure] = []
        self.runs: dict[str, AgentRun] = {}

    def upsert_lead(self, lead: Lead) -> Lead:
        with self._lock:
            lead.updated_at = utcnow()
            self.leads[lead.lead_id] = lead.model_copy(deep=True)
            return lead

    def get_lead(self, lead_id: str) -> Optional[Lead]:
        with self._lock:
            lead = self.leads.get(lead_id)
            return lead.model_copy(deep=True) if lead else None

    def list_leads(self, status: Optional[LeadStatus] = None, limit: int = 50) -> list[Lead]:
        with self._lock:
            items = list(self.leads.values())
            if status is not None:
                items = [lead for lead in items if lead.status == status]
            items.sort(key=lambda lead: lead.created_at)
            return [lead.model_copy(deep=True) for lead in items[:limit]]

    def set_lead_status(self, lead_id: str, status: LeadStatus) -> None:
        with self._lock:
            lead = self.leads.get(lead_id)
            if lead:
                lead.status = status
                lead.updated_at = utcnow()

    def cached_context(self, lead: Lead) -> str:
        with self._lock:
            stored = self.leads.get(lead.lead_id)
            if stored and stored.cached_context:
                return stored.cached_context
            return lead.cached_context

    def save_cached_context(self, lead_id: str, context: str) -> None:
        with self._lock:
            lead = self.leads.get(lead_id)
            if lead:
                lead.cached_context = context
                lead.updated_at = utcnow()

    def log_event(self, event: OutreachEvent) -> None:
        with self._lock:
            self.events.append(event.model_copy(deep=True))

    def latest_event(self, lead_id: str) -> Optional[OutreachEvent]:
        with self._lock:
            matches = [event for event in self.events if event.lead_id == lead_id]
            return matches[-1].model_copy(deep=True) if matches else None

    def list_patterns(self) -> list[MessagePattern]:
        with self._lock:
            patterns = [p.model_copy(deep=True) for p in self.patterns.values()]
            patterns.sort(key=lambda p: p.score, reverse=True)
            return patterns

    def upsert_pattern(self, pattern: MessagePattern) -> None:
        with self._lock:
            pattern.updated_at = utcnow()
            self.patterns[pattern.pattern_id] = pattern.model_copy(deep=True)

    def get_weights(self) -> dict[str, float]:
        with self._lock:
            return dict(self.weights)

    def set_weights(self, weights: dict[str, float]) -> None:
        with self._lock:
            self.weights = dict(weights)
            self.weight_version += 1

    def list_weight_rows(self) -> list[IcpWeight]:
        with self._lock:
            now = utcnow()
            return [
                IcpWeight(
                    feature=feature,
                    weight=weight,
                    version=self.weight_version,
                    updated_at=now,
                )
                for feature, weight in self.weights.items()
            ]

    def log_tool_failure(self, failure: ToolFailure) -> None:
        with self._lock:
            self.failures.append(failure.model_copy(deep=True))

    def list_tool_failures(self, run_id: Optional[str] = None) -> list[ToolFailure]:
        with self._lock:
            items = self.failures
            if run_id:
                items = [row for row in items if row.run_id == run_id]
            return deepcopy(items)

    def log_run(self, run: AgentRun) -> None:
        with self._lock:
            self.runs[run.run_id] = run.model_copy(deep=True)

    def get_run(self, run_id: str) -> Optional[AgentRun]:
        with self._lock:
            run = self.runs.get(run_id)
            return run.model_copy(deep=True) if run else None
