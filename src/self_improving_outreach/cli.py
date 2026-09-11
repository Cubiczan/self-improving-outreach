"""CLI: run one lead, learn from an outcome, swarm the queue, migrate ClickHouse."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from self_improving_outreach import brand
from self_improving_outreach.config import get_settings, reset_settings_cache
from self_improving_outreach.learning.learner import apply_learn_event
from self_improving_outreach.models import LearnEvent, Outcome
from self_improving_outreach.runtime import SAMPLE_QUEUE, build_runtime, build_swarm
from self_improving_outreach.swarm.queue import lead_from_mapping
from self_improving_outreach.voice.livekit_agent import describe_status, record_voice_feedback

app = typer.Typer(
    help=f"{brand.BRAND} self-improving outreach crews. Drafts + learns; Pipeline Scout sends.",
    no_args_is_help=True,
)
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
    """Apply an explicit outcome (thumbs, reply, meeting, ignore) to weights + patterns."""
    if not event and not event_file:
        raise typer.BadParameter("Provide --event JSON or --event-file")
    payload = json.loads(event_file.read_text(encoding="utf-8") if event_file else event)
    learn_event = LearnEvent.model_validate(payload)
    runtime = build_runtime()
    store = runtime["store"]
    lead = store.get_lead(learn_event.lead_id)
    weights = apply_learn_event(store, learn_event, lead)
    console.print({"weights": weights, "top_patterns": [p.pattern_id for p in store.list_patterns()[:5]]})


@app.command()
def swarm(
    concurrency: int = typer.Option(5, help="Parallel CrewAI/mock crews"),
    once: bool = typer.Option(False, "--once", help="Process one batch and exit"),
    loop: bool = typer.Option(False, "--loop", help="Keep claiming the queue"),
    interval: int = typer.Option(300, help="Seconds between loop batches"),
    queue: Optional[Path] = typer.Option(None, help="JSON queue path (mock default: data/leads.sample.json)"),
    max_leads: Optional[int] = typer.Option(None, help="Cap leads in this batch"),
    max_batches: Optional[int] = typer.Option(None, help="Cap loop iterations (tests)"),
) -> None:
    """Run N parallel closed-loop crews over the ClickHouse or JSON lead queue."""
    if loop and once:
        raise typer.BadParameter("Choose either --once or --loop")
    if not loop:
        once = True
    settings = get_settings()
    orchestrator = build_swarm(
        settings,
        concurrency=concurrency,
        queue_path=str(queue) if queue else None,
    )
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
) -> None:
    """Optional LiveKit module. Without keys, records mock interview feedback only."""
    settings = get_settings()
    console.print(describe_status(settings))
    if not lead_id:
        return
    runtime = build_runtime(settings)
    lead = runtime["store"].get_lead(lead_id)
    if lead is None:
        raise typer.BadParameter(f"Unknown lead_id {lead_id}")
    weights = record_voice_feedback(runtime["store"], lead, positive=positive, notes=notes)
    console.print({"weights": weights})


@app.command("show-config")
def show_config() -> None:
    """Print non-secret configuration (never prints key material)."""
    reset_settings_cache()
    settings = get_settings()
    console.print(
        {
            "brand": brand.BRAND,
            "mock_mode": settings.is_mock,
            "you_com_configured": bool(settings.you_key),
            "clickhouse_configured": bool(settings.clickhouse_host),
            "daytona_configured": bool(settings.daytona_api_key),
            "livekit_configured": bool(settings.livekit_api_key),
            "crewai": settings.use_crewai,
            "sample_queue": str(SAMPLE_QUEUE),
        }
    )


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
