"""ClickHouse Cloud / local HTTP store via clickhouse-connect."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from self_improving_outreach.config import Settings
from self_improving_outreach.learning.defaults import default_patterns, default_weights
from self_improving_outreach.models import (
    AgentRun,
    Channel,
    IcpWeight,
    Lead,
    LeadStatus,
    MessagePattern,
    Outcome,
    OutreachEvent,
    ToolFailure,
    utcnow,
)
from self_improving_outreach.stores.memory import MemoryStore


def _json(value: Any) -> str:
    return json.dumps(value, default=str)


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


class ClickHouseStore:
    """Persists learning tables in ClickHouse; seeds defaults on first use."""

    def __init__(self, client: Any, database: str) -> None:
        self._client = client
        self._database = database
        self._seeded = False

    @classmethod
    def from_settings(cls, settings: Settings) -> "ClickHouseStore":
        try:
            import clickhouse_connect
        except ImportError as exc:
            raise RuntimeError(
                "clickhouse-connect is not installed. "
                "Run: uv sync --extra clickhouse"
            ) from exc
        client = clickhouse_connect.get_client(
            host=settings.clickhouse_host,
            port=settings.clickhouse_port,
            username=settings.clickhouse_user,
            password=settings.clickhouse_password or "",
            database=settings.clickhouse_database,
            secure=settings.clickhouse_secure,
        )
        return cls(client, settings.clickhouse_database)

    def _q(self, sql: str, parameters: Optional[dict[str, Any]] = None):
        return self._client.query(sql, parameters=parameters)

    def _ensure_seed(self) -> None:
        if self._seeded:
            return
        existing = self._q("SELECT count() FROM icp_weights").result_rows[0][0]
        if existing == 0:
            now = utcnow()
            self._client.insert(
                "icp_weights",
                [(feature, weight, now, 1) for feature, weight in default_weights().items()],
                column_names=["feature", "weight", "updated_at", "version"],
            )
        patterns_count = self._q("SELECT count() FROM message_patterns").result_rows[0][0]
        if patterns_count == 0:
            rows = []
            for pattern in default_patterns():
                rows.append(
                    (
                        pattern.pattern_id,
                        pattern.angle,
                        pattern.channel.value,
                        pattern.template,
                        pattern.wins,
                        pattern.losses,
                        pattern.impressions,
                        pattern.score,
                        pattern.updated_at,
                    )
                )
            self._client.insert(
                "message_patterns",
                rows,
                column_names=[
                    "pattern_id",
                    "angle",
                    "channel",
                    "template",
                    "wins",
                    "losses",
                    "impressions",
                    "score",
                    "updated_at",
                ],
            )
        self._seeded = True

    def upsert_lead(self, lead: Lead) -> Lead:
        self._ensure_seed()
        lead.updated_at = utcnow()
        self._client.insert(
            "leads",
            [
                (
                    lead.lead_id,
                    lead.company,
                    lead.domain,
                    lead.contact_name,
                    lead.title,
                    lead.industry,
                    lead.location,
                    _json(lead.signals),
                    lead.cached_context,
                    lead.status.value,
                    lead.created_at,
                    lead.updated_at,
                )
            ],
            column_names=[
                "lead_id",
                "company",
                "domain",
                "contact_name",
                "title",
                "industry",
                "location",
                "signals",
                "cached_context",
                "status",
                "created_at",
                "updated_at",
            ],
        )
        return lead

    def get_lead(self, lead_id: str) -> Optional[Lead]:
        self._ensure_seed()
        result = self._q(
            "SELECT * FROM leads FINAL WHERE lead_id = {id:String} LIMIT 1",
            {"id": lead_id},
        )
        return self._lead_from_row(result) if result.result_rows else None

    def list_leads(self, status: Optional[LeadStatus] = None, limit: int = 50) -> list[Lead]:
        self._ensure_seed()
        if status is None:
            result = self._q(
                "SELECT * FROM leads FINAL ORDER BY created_at ASC LIMIT {lim:UInt32}",
                {"lim": limit},
            )
        else:
            result = self._q(
                "SELECT * FROM leads FINAL WHERE status = {s:String} "
                "ORDER BY created_at ASC LIMIT {lim:UInt32}",
                {"s": status.value, "lim": limit},
            )
        leads = []
        names = result.column_names
        for row in result.result_rows:
            leads.append(self._lead_from_mapping(dict(zip(names, row))))
        return leads

    def set_lead_status(self, lead_id: str, status: LeadStatus) -> None:
        lead = self.get_lead(lead_id)
        if lead:
            lead.status = status
            self.upsert_lead(lead)

    def cached_context(self, lead: Lead) -> str:
        stored = self.get_lead(lead.lead_id)
        if stored and stored.cached_context:
            return stored.cached_context
        return lead.cached_context

    def save_cached_context(self, lead_id: str, context: str) -> None:
        lead = self.get_lead(lead_id)
        if lead:
            lead.cached_context = context
            self.upsert_lead(lead)

    def log_event(self, event: OutreachEvent) -> None:
        self._ensure_seed()
        self._client.insert(
            "outreach_events",
            [
                (
                    event.event_id,
                    event.lead_id,
                    event.run_id,
                    event.channel.value,
                    event.outcome.value,
                    event.angle,
                    event.pattern_id,
                    event.body,
                    _json(event.metadata),
                    event.created_at,
                )
            ],
            column_names=[
                "event_id",
                "lead_id",
                "run_id",
                "channel",
                "outcome",
                "angle",
                "pattern_id",
                "body",
                "metadata",
                "created_at",
            ],
        )

    def latest_event(self, lead_id: str) -> Optional[OutreachEvent]:
        self._ensure_seed()
        result = self._q(
            "SELECT * FROM outreach_events WHERE lead_id = {id:String} "
            "ORDER BY created_at DESC LIMIT 1",
            {"id": lead_id},
        )
        if not result.result_rows:
            return None
        row = dict(zip(result.column_names, result.result_rows[0]))
        meta = row.get("metadata") or "{}"
        if isinstance(meta, str):
            meta = json.loads(meta or "{}")
        return OutreachEvent(
            event_id=str(row["event_id"]),
            lead_id=str(row["lead_id"]),
            run_id=str(row["run_id"]),
            channel=Channel(row["channel"]),
            outcome=Outcome(row["outcome"]),
            angle=row["angle"],
            pattern_id=row["pattern_id"],
            body=row["body"],
            metadata=meta,
            created_at=_parse_dt(row["created_at"]),
        )

    def list_patterns(self) -> list[MessagePattern]:
        self._ensure_seed()
        result = self._q(
            "SELECT * FROM message_patterns FINAL ORDER BY score DESC, pattern_id ASC"
        )
        patterns = []
        for row in result.result_rows:
            mapping = dict(zip(result.column_names, row))
            patterns.append(
                MessagePattern(
                    pattern_id=mapping["pattern_id"],
                    angle=mapping["angle"],
                    channel=Channel(mapping["channel"]),
                    template=mapping["template"],
                    wins=int(mapping["wins"]),
                    losses=int(mapping["losses"]),
                    impressions=int(mapping["impressions"]),
                    score=float(mapping["score"]),
                    updated_at=_parse_dt(mapping["updated_at"]),
                )
            )
        return patterns

    def upsert_pattern(self, pattern: MessagePattern) -> None:
        self._ensure_seed()
        pattern.updated_at = utcnow()
        self._client.insert(
            "message_patterns",
            [
                (
                    pattern.pattern_id,
                    pattern.angle,
                    pattern.channel.value,
                    pattern.template,
                    pattern.wins,
                    pattern.losses,
                    pattern.impressions,
                    pattern.score,
                    pattern.updated_at,
                )
            ],
            column_names=[
                "pattern_id",
                "angle",
                "channel",
                "template",
                "wins",
                "losses",
                "impressions",
                "score",
                "updated_at",
            ],
        )

    def get_weights(self) -> dict[str, float]:
        self._ensure_seed()
        result = self._q("SELECT feature, weight FROM icp_weights FINAL")
        return {row[0]: float(row[1]) for row in result.result_rows}

    def set_weights(self, weights: dict[str, float]) -> None:
        self._ensure_seed()
        now = utcnow()
        version = int(self._q("SELECT max(version) FROM icp_weights").result_rows[0][0] or 0) + 1
        self._client.insert(
            "icp_weights",
            [(feature, weight, now, version) for feature, weight in weights.items()],
            column_names=["feature", "weight", "updated_at", "version"],
        )

    def list_weight_rows(self) -> list[IcpWeight]:
        self._ensure_seed()
        result = self._q("SELECT feature, weight, version, updated_at FROM icp_weights FINAL")
        return [
            IcpWeight(
                feature=row[0],
                weight=float(row[1]),
                version=int(row[2]),
                updated_at=_parse_dt(row[3]),
            )
            for row in result.result_rows
        ]

    def log_tool_failure(self, failure: ToolFailure) -> None:
        self._ensure_seed()
        self._client.insert(
            "tool_failures",
            [
                (
                    failure.failure_id,
                    failure.run_id,
                    failure.tool_name,
                    failure.error_class,
                    failure.message,
                    failure.retry_attempt,
                    1 if failure.degraded else 0,
                    failure.created_at,
                )
            ],
            column_names=[
                "failure_id",
                "run_id",
                "tool_name",
                "error_class",
                "message",
                "retry_attempt",
                "degraded",
                "created_at",
            ],
        )

    def list_tool_failures(self, run_id: Optional[str] = None) -> list[ToolFailure]:
        self._ensure_seed()
        if run_id:
            result = self._q(
                "SELECT * FROM tool_failures WHERE run_id = {id:String} ORDER BY created_at",
                {"id": run_id},
            )
        else:
            result = self._q("SELECT * FROM tool_failures ORDER BY created_at")
        failures = []
        for row in result.result_rows:
            mapping = dict(zip(result.column_names, row))
            failures.append(
                ToolFailure(
                    failure_id=str(mapping["failure_id"]),
                    run_id=str(mapping["run_id"]),
                    tool_name=mapping["tool_name"],
                    error_class=mapping["error_class"],
                    message=mapping["message"],
                    retry_attempt=int(mapping["retry_attempt"]),
                    degraded=bool(mapping["degraded"]),
                    created_at=_parse_dt(mapping["created_at"]),
                )
            )
        return failures

    def log_run(self, run: AgentRun) -> None:
        self._ensure_seed()
        self._client.insert(
            "agent_runs",
            [
                (
                    run.run_id,
                    run.swarm_id or "",
                    run.lead_id,
                    run.status,
                    _json(run.traces),
                    run.worker_id,
                    run.error or "",
                    run.started_at,
                    run.finished_at or utcnow(),
                )
            ],
            column_names=[
                "run_id",
                "swarm_id",
                "lead_id",
                "status",
                "traces",
                "worker_id",
                "error",
                "started_at",
                "finished_at",
            ],
        )

    def get_run(self, run_id: str) -> Optional[AgentRun]:
        self._ensure_seed()
        result = self._q(
            "SELECT * FROM agent_runs WHERE run_id = {id:String} ORDER BY started_at DESC LIMIT 1",
            {"id": run_id},
        )
        if not result.result_rows:
            return None
        mapping = dict(zip(result.column_names, result.result_rows[0]))
        traces = mapping.get("traces") or "[]"
        if isinstance(traces, str):
            traces = json.loads(traces or "[]")
        finished = mapping.get("finished_at")
        return AgentRun(
            run_id=str(mapping["run_id"]),
            swarm_id=mapping.get("swarm_id") or None,
            lead_id=str(mapping["lead_id"]),
            status=mapping["status"],
            traces=traces,
            worker_id=mapping.get("worker_id") or "",
            error=mapping.get("error") or None,
            started_at=_parse_dt(mapping["started_at"]),
            finished_at=_parse_dt(finished) if finished else None,
        )

    def _lead_from_row(self, result: Any) -> Lead:
        mapping = dict(zip(result.column_names, result.result_rows[0]))
        return self._lead_from_mapping(mapping)

    def _lead_from_mapping(self, mapping: dict[str, Any]) -> Lead:
        signals = mapping.get("signals") or "{}"
        if isinstance(signals, str):
            signals = json.loads(signals or "{}")
        return Lead(
            lead_id=str(mapping["lead_id"]),
            company=mapping["company"],
            domain=mapping.get("domain") or "",
            contact_name=mapping.get("contact_name") or "",
            title=mapping.get("title") or "",
            industry=mapping.get("industry") or "",
            location=mapping.get("location") or "",
            signals=signals,
            cached_context=mapping.get("cached_context") or "",
            status=LeadStatus(mapping["status"]),
            created_at=_parse_dt(mapping["created_at"]),
            updated_at=_parse_dt(mapping["updated_at"]),
        )


def build_store(settings: Settings):
    """ClickHouse when configured and importable; otherwise MemoryStore."""
    if not settings.clickhouse_host:
        return MemoryStore()
    try:
        return ClickHouseStore.from_settings(settings)
    except Exception:
        return MemoryStore()
