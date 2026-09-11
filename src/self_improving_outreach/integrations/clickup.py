"""Map ClickUp task / webhook JSON onto a queued Cubiczan lead.

Search + outreach only. Pipeline Scout / Marketing Hunter call the CLI when a
task lands in status=Queued. No Google Ads, Facebook Ads, or Meta Ads paths.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Protocol

from pydantic import BaseModel, Field

from self_improving_outreach.config import Settings
from self_improving_outreach.models import Lead, LeadStatus

logger = logging.getLogger(__name__)

QUEUED_STATUS = "queued"
CLICKUP_API_BASE = "https://api.clickup.com/api/v2"
DEFAULT_SALES_LEADS_LIST_ID = "901716996906"
IN_FLIGHT = {
    LeadStatus.PROCESSING,
    LeadStatus.DRAFTED,
    LeadStatus.PENDING_REVIEW,
    LeadStatus.APPROVED_FOR_SCOUT,
    LeadStatus.LEARNED,
    LeadStatus.FAILED,
}

_COMPANY_KEYS = frozenset(
    {"company", "company_name", "account", "account_name", "org", "organization"}
)
_CONTACT_KEYS = frozenset(
    {"contact", "contact_name", "full_name", "person", "prospect", "ae_contact"}
)
_TITLE_KEYS = frozenset({"title", "job_title", "role", "job"})
_INDUSTRY_KEYS = frozenset({"industry", "vertical", "sector"})
_DOMAIN_KEYS = frozenset({"domain", "website", "company_domain"})
_LOCATION_KEYS = frozenset({"location", "city", "hq"})
_PAIN_KEYS = frozenset({"pain", "signal", "signals", "notes", "why", "hook"})


class ClickUpIngestResult(BaseModel):
    lead: Lead | None = None
    skipped: bool = False
    reason: str = ""
    clickup_task_id: str = ""
    status: str = ""


def unwrap_clickup_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Flatten a webhook envelope (`task`, `payload`) into a task-shaped dict."""
    if not isinstance(data, dict):
        raise TypeError("ClickUp payload must be a JSON object")
    task: dict[str, Any] = {}
    nested = data.get("task")
    if isinstance(nested, dict):
        task.update(nested)
    inner = data.get("payload")
    if isinstance(inner, dict):
        if isinstance(inner.get("task"), dict):
            task.update(inner["task"])
        else:
            for key, value in inner.items():
                if key not in task:
                    task[key] = value
    passthrough = (
        "id",
        "task_id",
        "name",
        "status",
        "custom_fields",
        "description",
        "url",
        "company",
        "contact_name",
        "title",
        "industry",
        "domain",
        "location",
        "signals",
        "lead_id",
        "text_content",
    )
    for key in passthrough:
        if key in data and key not in task:
            task[key] = data[key]
    if "id" not in task and data.get("task_id"):
        task["id"] = data["task_id"]
    if "task_id" not in task and task.get("id"):
        task["task_id"] = task["id"]
    return task


def clickup_status_name(task: dict[str, Any]) -> str:
    status = task.get("status")
    if isinstance(status, dict):
        return str(status.get("status") or status.get("type") or "").strip()
    if status is None:
        return ""
    return str(status).strip()


def is_queued_status(status: str) -> bool:
    return status.strip().lower() == QUEUED_STATUS


def _field_value(field: dict[str, Any]) -> Any:
    value = field.get("value")
    if isinstance(value, dict):
        return (
            value.get("name")
            or value.get("value")
            or value.get("email")
            or value.get("username")
            or ""
        )
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, dict):
                part = item.get("name") or item.get("email") or item.get("username") or ""
                if part:
                    parts.append(str(part))
            elif item not in (None, ""):
                parts.append(str(item))
        return ", ".join(parts)
    return value


def _custom_fields_map(task: dict[str, Any]) -> dict[str, Any]:
    raw = task.get("custom_fields") or []
    mapped: dict[str, Any] = {}
    if not isinstance(raw, list):
        return mapped
    for field in raw:
        if not isinstance(field, dict):
            continue
        name = str(field.get("name") or field.get("field_name") or "").strip()
        if not name:
            continue
        mapped[name.lower()] = _field_value(field)
    return mapped


def _first_field(fields: dict[str, Any], keys: frozenset[str]) -> str:
    for key in keys:
        value = fields.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _split_task_name(name: str) -> tuple[str, str]:
    text = (name or "").strip()
    for sep in (" — ", " – ", " - ", ": "):
        if sep in text:
            left, right = text.split(sep, 1)
            return left.strip(), right.strip()
    return text, ""


def lead_from_clickup(data: dict[str, Any], *, force: bool = False) -> ClickUpIngestResult:
    """Build a queued Lead from ClickUp task JSON. Skips non-Queued unless force."""
    task = unwrap_clickup_payload(data)
    status = clickup_status_name(task)
    task_id = str(task.get("id") or task.get("task_id") or "").strip()
    if not is_queued_status(status) and not force:
        return ClickUpIngestResult(
            skipped=True,
            reason=f"status {status or '(empty)'} is not Queued (pass --force to ingest)",
            clickup_task_id=task_id,
            status=status,
        )

    fields = _custom_fields_map(task)
    name = str(task.get("name") or "").strip()
    company_from_name, contact_from_name = _split_task_name(name)

    company = (
        str(task.get("company") or "").strip()
        or _first_field(fields, _COMPANY_KEYS)
        or company_from_name
    )
    contact = (
        str(task.get("contact_name") or "").strip()
        or _first_field(fields, _CONTACT_KEYS)
        or contact_from_name
    )
    if not company:
        raise ValueError(
            "ClickUp payload needs a company (custom field, company key, or task name)"
        )

    description = str(task.get("description") or task.get("text_content") or "").strip()
    pain = _first_field(fields, _PAIN_KEYS)
    signals: dict[str, Any] = {}
    raw_signals = task.get("signals")
    if isinstance(raw_signals, dict):
        signals.update(raw_signals)
    if pain and "pain" not in signals:
        signals["pain"] = pain
    if task_id:
        signals["clickup_task_id"] = task_id
    url = str(task.get("url") or "").strip()
    if url:
        signals["clickup_url"] = url

    lead_id = str(task.get("lead_id") or "").strip() or (f"clickup-{task_id}" if task_id else "")
    lead_kwargs: dict[str, Any] = {
        "company": company,
        "domain": str(task.get("domain") or "").strip() or _first_field(fields, _DOMAIN_KEYS),
        "contact_name": contact,
        "title": str(task.get("title") or "").strip() or _first_field(fields, _TITLE_KEYS),
        "industry": str(task.get("industry") or "").strip() or _first_field(fields, _INDUSTRY_KEYS),
        "location": str(task.get("location") or "").strip() or _first_field(fields, _LOCATION_KEYS),
        "signals": signals,
        "cached_context": description,
        "status": LeadStatus.QUEUED,
    }
    if lead_id:
        lead_kwargs["lead_id"] = lead_id
    lead = Lead.model_validate(lead_kwargs)
    return ClickUpIngestResult(
        lead=lead,
        skipped=False,
        clickup_task_id=task_id,
        status=status or QUEUED_STATUS,
    )


def ingest_clickup_payload(
    store,
    data: dict[str, Any],
    *,
    force: bool = False,
    reset_status: bool = True,
) -> ClickUpIngestResult:
    result = lead_from_clickup(data, force=force)
    if result.skipped or result.lead is None:
        return result
    existing = store.get_lead(result.lead.lead_id)
    if existing is not None and not reset_status and existing.status in IN_FLIGHT:
        result.lead.status = existing.status
        result.lead.signals = {**existing.signals, **result.lead.signals}
        if existing.cached_context and not result.lead.cached_context:
            result.lead.cached_context = existing.cached_context
    store.upsert_lead(result.lead)
    stored = store.get_lead(result.lead.lead_id) or result.lead
    return result.model_copy(update={"lead": stored})


class ClickUpPollReport(BaseModel):
    list_id: str
    status: str
    fetched: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    lead_ids: list[str] = Field(default_factory=list)
    dry_run: bool = False


class ClickUpClient(Protocol):
    def list_tasks(self, list_id: str, statuses: list[str]) -> list[dict[str, Any]]: ...


class MockClickUpClient:
    """In-memory ClickUp client for CI. No HTTP."""

    def __init__(self, tasks: Optional[list[dict[str, Any]]] = None) -> None:
        self.tasks = list(tasks or [])
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    def list_tasks(self, list_id: str, statuses: list[str]) -> list[dict[str, Any]]:
        self.calls.append((list_id, tuple(statuses)))
        wanted = {item.strip().lower() for item in statuses}
        rows = []
        for task in self.tasks:
            status = clickup_status_name(task)
            if not wanted or status.lower() in wanted:
                rows.append(task)
        return rows


class HttpClickUpClient:
    def __init__(self, token: str, *, base_url: str = CLICKUP_API_BASE, timeout: float = 30.0) -> None:
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def list_tasks(self, list_id: str, statuses: list[str]) -> list[dict[str, Any]]:
        import httpx

        tasks: list[dict[str, Any]] = []
        page = 0
        while True:
            params: list[tuple[str, str]] = [("page", str(page)), ("include_closed", "false")]
            for status in statuses:
                params.append(("statuses[]", status))
            response = httpx.get(
                f"{self.base_url}/list/{list_id}/task",
                headers={"Authorization": self.token, "Accept": "application/json"},
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            batch = payload.get("tasks") or []
            tasks.extend(batch)
            if payload.get("last_page") or not batch:
                break
            page += 1
        return tasks


def build_clickup_client(settings: Settings, client: Optional[ClickUpClient] = None) -> Optional[ClickUpClient]:
    if client is not None:
        return client
    if not settings.clickup_api_token:
        return None
    return HttpClickUpClient(settings.clickup_api_token)


def sync_clickup_list(
    store,
    client: ClickUpClient,
    *,
    list_id: str = DEFAULT_SALES_LEADS_LIST_ID,
    status: str = "Queued",
    dry_run: bool = False,
) -> ClickUpPollReport:
    """Poll a ClickUp list into the store. Reuses lead_from_clickup; does not reset in-flight."""
    report = ClickUpPollReport(list_id=list_id, status=status, dry_run=dry_run)
    tasks = client.list_tasks(list_id, [status])
    report.fetched = len(tasks)
    for task in tasks:
        try:
            mapped = lead_from_clickup(task)
        except (TypeError, ValueError) as exc:
            logger.warning("Skipping ClickUp task: %s", exc)
            report.skipped += 1
            continue
        if mapped.skipped or mapped.lead is None:
            report.skipped += 1
            continue
        existing = store.get_lead(mapped.lead.lead_id)
        if dry_run:
            report.lead_ids.append(mapped.lead.lead_id)
            if existing is None:
                report.created += 1
            else:
                report.updated += 1
            continue
        ingest_clickup_payload(store, task, reset_status=False)
        report.lead_ids.append(mapped.lead.lead_id)
        if existing is None:
            report.created += 1
        else:
            report.updated += 1
    return report
