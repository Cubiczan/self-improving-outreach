"""CLI: run one lead, learn from an outcome, swarm the queue, migrate ClickHouse."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from self_improving_outreach import brand
from self_improving_outreach.config import get_settings, public_settings_view, reset_settings_cache
from self_improving_outreach.integrations.clickup import ingest_clickup_payload, sync_clickup_list
from self_improving_outreach.learning.learner import apply_learn_event
from self_improving_outreach.models import LeadStatus, LearnEvent, Outcome
from self_improving_outreach.runtime import build_runtime, build_swarm
from self_improving_outreach.swarm.queue import (
    JsonLeadQueue,
    lead_from_mapping,
    mappings_from_json_payload,
    parse_requeue_status,
    requeue_leads,
    resolve_lead_from_sample,
    upsert_leads_from_mappings,
)
from self_improving_outreach.voice.livekit_agent import (
    describe_status,
    record_transcript_feedback,
    record_voice_feedback,
)
from self_improving_outreach.voice.transcript import parse_voice_transcript_file

app = typer.Typer(
    help=f"{brand.BRAND} self-improving outreach crews. Drafts + learns; Pipeline Scout sends.",
    no_args_is_help=True,
)
queue_app = typer.Typer(
    help="Reclaim or upsert leads on the ClickHouse / JSON queue (search + outreach only).",
    no_args_is_help=True,
)
app.add_typer(queue_app, name="queue")
console = Console()


def _dump(model) -> None:
    console.print_json(model.model_dump_json(indent=2))


@app.callback()
def _root() -> None:
    """Cubiczan outreach agent CLI."""


@app.command()
def run(
    lead: Optional[str] = typer.Option(None, help="JSON object for a single lead"),
    lead_file: Optional[Path] = typer.Option(None, help="Path to a JSON lead object"),
    outcome: Optional[str] = typer.Option(None, help="Optional outcome to learn immediately"),
) -> None:
    """Run Researcher → Scorer → Drafter → Critic for one lead."""
    if not lead and not lead_file:
        raise typer.BadParameter("Provide --lead JSON or --lead-file")
    payload = json.loads(lead_file.read_text(encoding="utf-8") if lead_file else lead)
    runtime = build_runtime()
    result = runtime["pipeline"].run(
        lead_from_mapping(payload),
        outcome=Outcome(outcome) if outcome else None,
    )
    _dump(result)


@app.command()
def learn(
    event: Optional[str] = typer.Option(None, help="JSON LearnEvent"),
    event_file: Optional[Path] = typer.Option(None),
) -> None:
    """Apply a Scout outcome: thumbs_up/down, replied, meeting, ignore, sent."""
    if not event and not event_file:
        raise typer.BadParameter("Provide --event JSON or --event-file")
    payload = json.loads(event_file.read_text(encoding="utf-8") if event_file else event)
    learn_event = LearnEvent.model_validate(payload)
    runtime = build_runtime()
    store = runtime["store"]
    lead = resolve_lead_from_sample(store, learn_event.lead_id)
    if lead is None and not learn_event.features and not learn_event.pattern_id:
        raise typer.BadParameter(f"Unknown lead_id {learn_event.lead_id}")
    weights = apply_learn_event(store, learn_event, lead)
    console.print(
        {
            "weights": weights,
            "top_patterns": [p.pattern_id for p in store.list_patterns()[:5]],
            "lead_id": lead.lead_id if lead else learn_event.lead_id,
            "outcome": learn_event.outcome.value,
        }
    )


@app.command()
def swarm(
    concurrency: int = typer.Option(5, help="Parallel CrewAI/mock crews"),
    once: bool = typer.Option(False, "--once", help="Process one batch and exit"),
    loop: bool = typer.Option(False, "--loop", help="Keep claiming the queue"),
    interval: int = typer.Option(300, help="Seconds between loop batches"),
    queue: Optional[Path] = typer.Option(None, help="JSON queue path (mock default: data/leads.sample.json)"),
    max_leads: Optional[int] = typer.Option(None, help="Cap leads in this batch"),
    max_batches: Optional[int] = typer.Option(None, help="Cap loop iterations (tests)"),
    learn_simulated: bool = typer.Option(
        False,
        "--learn-simulated",
        help="After draft, apply simulate_outcome (demo). Live drafted does not invent CRM replies unless set.",
    ),
    requeue: bool = typer.Option(
        False,
        "--requeue",
        help="Set processing/failed leads back to queued before claiming",
    ),
) -> None:
    """Run N parallel closed-loop crews over the ClickHouse or JSON lead queue."""
    if loop and once:
        raise typer.BadParameter("Choose either --once or --loop")
    if not loop:
        once = True
    settings = get_settings()
    if learn_simulated:
        settings = settings.model_copy(update={"learn_on_draft": True})
    orchestrator = build_swarm(
        settings,
        concurrency=concurrency,
        queue_path=str(queue) if queue else None,
    )
    if requeue:
        reclaimed = requeue_leads(
            orchestrator.store,
            statuses={LeadStatus.PROCESSING, LeadStatus.FAILED},
        )
        console.print(f"Requeued {len(reclaimed)} processing/failed leads")
    if once:
        report = orchestrator.run_once(max_leads=max_leads)
        _print_swarm(report)
        return
    console.print(
        f"[bold]{brand.BRAND}[/bold] swarm looping every {interval}s "
        f"(concurrency={concurrency}). Ctrl+C to stop."
    )
    try:
        reports = orchestrator.run_loop(interval, max_batches=max_batches)
        for report in reports:
            _print_swarm(report)
    except KeyboardInterrupt:
        console.print("swarm stopped")


@app.command()
def migrate(
    sql_path: Path = typer.Option(
        Path("migrations/clickhouse/001_init.sql"),
        help="ClickHouse DDL file",
    ),
) -> None:
    """Apply ClickHouse schema. Creates the database if it is missing."""
    settings = get_settings()
    if not settings.clickhouse_host:
        console.print("ClickHouse not configured; using in-memory store. Skip migrate.")
        raise typer.Exit(0)
    from self_improving_outreach.stores.clickhouse import apply_clickhouse_migration

    applied = apply_clickhouse_migration(settings, sql_path)
    console.print(f"Applied {applied} statements to {settings.clickhouse_database}")


@app.command()
def voice(
    lead_id: Optional[str] = typer.Option(None),
    positive: bool = typer.Option(True, help="Mock interview: thumbs up/down into Learner"),
    notes: str = typer.Option("voice preference interview"),
    transcript_file: Optional[Path] = typer.Option(
        None,
        "--transcript-file",
        help="JSON interview transcript (positive/negative, notes, pattern_id)",
    ),
) -> None:
    """Optional LiveKit module. Without keys, records mock interview feedback only."""
    settings = get_settings()
    console.print(describe_status(settings))
    feedback = None
    if transcript_file is not None:
        feedback = parse_voice_transcript_file(transcript_file)
        lead_id = lead_id or feedback.lead_id
        positive = feedback.positive
        notes = feedback.notes or notes
    if not lead_id:
        return
    runtime = build_runtime(settings)
    lead = _resolve_voice_lead(runtime["store"], lead_id)
    if lead is None:
        raise typer.BadParameter(f"Unknown lead_id {lead_id}")
    if feedback is not None:
        weights = record_transcript_feedback(runtime["store"], lead, feedback)
    else:
        weights = record_voice_feedback(runtime["store"], lead, positive=positive, notes=notes)
    console.print({"weights": weights, "source": "livekit", "positive": positive})


@app.command("show-config")
def show_config() -> None:
    """Print non-secret configuration (never prints key material)."""
    reset_settings_cache()
    console.print(public_settings_view(get_settings()))


@app.command()
def requeue(
    lead_id: Optional[list[str]] = typer.Option(
        None,
        "--lead-id",
        help="Lead id to set back to queued (repeatable)",
    ),
    company: Optional[str] = typer.Option(None, help="Company substring (case-insensitive)"),
    all_sample: bool = typer.Option(False, "--all-sample", help="Reset data/leads.sample.json ICP leads"),
    clear_processing: bool = typer.Option(
        False,
        "--clear-processing",
        help="Set stuck processing leads back to queued",
    ),
    status: Optional[str] = typer.Option(
        None,
        "--status",
        help="processing | failed | done (drafted/approved/learned) or a LeadStatus value",
    ),
    queue: Optional[Path] = typer.Option(None, help="Persistable JSON queue (never overwrites the sample file)"),
) -> None:
    """Set leads back to queued so the swarm can claim them again."""
    _run_requeue(lead_id, company, all_sample, clear_processing, queue, status)


@queue_app.command("reset")
def queue_reset(
    lead_id: Optional[list[str]] = typer.Option(None, "--lead-id"),
    company: Optional[str] = typer.Option(None),
    all_sample: bool = typer.Option(False, "--all-sample"),
    clear_processing: bool = typer.Option(False, "--clear-processing"),
    status: Optional[str] = typer.Option(None, "--status"),
    queue: Optional[Path] = typer.Option(None),
) -> None:
    """Alias for requeue."""
    _run_requeue(lead_id, company, all_sample, clear_processing, queue, status)


@queue_app.command("upsert")
def queue_upsert(
    from_json: Optional[str] = typer.Option(None, "--from-json", help="Lead JSON object, list, or {leads: [...]}"),
    from_file: Optional[Path] = typer.Option(None, "--from-file", help="Path to the same JSON shapes"),
    queue: Optional[Path] = typer.Option(None, help="Persistable JSON queue"),
) -> None:
    """Upsert native lead JSON into the queue as queued (search + outreach; no ads)."""
    if not from_json and not from_file:
        raise typer.BadParameter("Provide --from-json or --from-file")
    payload = json.loads(from_file.read_text(encoding="utf-8") if from_file else from_json)
    store, json_queue = _store_with_optional_queue(queue)
    leads = upsert_leads_from_mappings(store, mappings_from_json_payload(payload), status=LeadStatus.QUEUED)
    _persist_queue(json_queue)
    console.print({"upserted": len(leads), "lead_ids": [lead.lead_id for lead in leads], "status": "queued"})


@app.command("ingest-clickup")
def ingest_clickup(
    json_payload: Optional[str] = typer.Option(None, "--json", help="ClickUp task or webhook JSON"),
    file: Optional[Path] = typer.Option(None, "--file", help="Path to ClickUp task / webhook JSON"),
    force: bool = typer.Option(False, "--force", help="Ingest even when status is not Queued"),
    queue: Optional[Path] = typer.Option(None, help="Persistable JSON queue"),
) -> None:
    """Ingest a ClickUp Queued task into the swarm queue. No paid ad spend paths."""
    if not json_payload and not file:
        raise typer.BadParameter("Provide --json or --file")
    payload = json.loads(file.read_text(encoding="utf-8") if file else json_payload)
    if not isinstance(payload, dict):
        raise typer.BadParameter("ClickUp payload must be a JSON object")
    store, json_queue = _store_with_optional_queue(queue)
    try:
        result = ingest_clickup_payload(store, payload, force=force)
    except (TypeError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    _persist_queue(json_queue)
    if result.skipped:
        console.print({"skipped": True, "reason": result.reason, "clickup_task_id": result.clickup_task_id})
        raise typer.Exit(0)
    lead = result.lead
    console.print(
        {
            "ingested": True,
            "lead_id": lead.lead_id if lead else None,
            "company": lead.company if lead else None,
            "status": lead.status.value if lead else None,
            "clickup_task_id": result.clickup_task_id,
        }
    )


@app.command("clickup-sync")
def clickup_sync(
    list_id: Optional[str] = typer.Option(
        None,
        help="ClickUp list id (default CLICKUP_LIST_ID / Sales Leads 901716996906)",
    ),
    status: Optional[str] = typer.Option(
        None,
        help="ClickUp task status to ingest (default Queued / CLICKUP_QUEUE_STATUS)",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Map tasks without writing the store"),
    queue: Optional[Path] = typer.Option(None, help="Persistable JSON queue"),
) -> None:
    """Poll ClickUp Queued tasks into the lead queue (idempotent by ClickUp task id)."""
    from self_improving_outreach.integrations.clickup import build_clickup_client

    settings = get_settings()
    client = build_clickup_client(settings)
    if client is None:
        console.print("CLICKUP_API_TOKEN not set; skip clickup-sync.")
        raise typer.Exit(0)
    store, json_queue = _store_with_optional_queue(queue)
    report = sync_clickup_list(
        store,
        client,
        list_id=list_id or settings.clickup_list_id,
        status=status or settings.clickup_queue_status,
        dry_run=dry_run,
    )
    _persist_queue(json_queue)
    console.print(report.model_dump())


def _store_with_optional_queue(queue: Optional[Path]):
    runtime = build_runtime()
    store = runtime["store"]
    json_queue = JsonLeadQueue(store, queue) if queue else None
    return store, json_queue


def _persist_queue(json_queue: Optional[JsonLeadQueue]) -> None:
    if json_queue is not None:
        json_queue.persist()


def _print_requeue(leads) -> None:
    table = Table(title=f"{brand.BRAND} requeue → {LeadStatus.QUEUED.value}")
    table.add_column("lead_id")
    table.add_column("company")
    table.add_column("status")
    for lead in leads:
        table.add_row(lead.lead_id, lead.company, lead.status.value)
    console.print(table)
    console.print({"requeued": len(leads), "lead_ids": [lead.lead_id for lead in leads]})


def _run_requeue(
    lead_id: Optional[list[str]],
    company: Optional[str],
    all_sample: bool,
    clear_processing: bool,
    queue: Optional[Path],
    status: Optional[str] = None,
) -> None:
    store, json_queue = _store_with_optional_queue(queue)
    try:
        statuses = parse_requeue_status(status) if status else None
        leads = requeue_leads(
            store,
            lead_ids=lead_id or None,
            company=company,
            all_sample=all_sample,
            clear_processing=clear_processing,
            statuses=statuses,
        )
    except (ValueError, KeyError, FileNotFoundError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    _persist_queue(json_queue)
    _print_requeue(leads)


def _resolve_voice_lead(store, lead_id: str):
    return resolve_lead_from_sample(store, lead_id)


def _print_swarm(report) -> None:
    table = Table(title=f"{brand.BRAND} swarm {report.swarm_id[:8]}")
    table.add_column("metric")
    table.add_column("value")
    table.add_row("processed", str(report.processed))
    table.add_row("succeeded", str(report.succeeded))
    table.add_row("failed", str(report.failed))
    table.add_row("degraded (You.com failover)", str(report.degraded))
    table.add_row("top_patterns", ", ".join(report.top_patterns))
    console.print(table)
    _dump(report)
