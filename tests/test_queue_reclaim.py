import json
from pathlib import Path

from typer.testing import CliRunner

from self_improving_outreach.cli import app
from self_improving_outreach.config import Settings
from self_improving_outreach.models import Lead, LeadStatus
from self_improving_outreach.runtime import SAMPLE_QUEUE, build_swarm
from self_improving_outreach.stores.memory import MemoryStore
from self_improving_outreach.swarm.queue import (
    JsonLeadQueue,
    load_json_leads,
    parse_requeue_status,
    requeue_leads,
)

runner = CliRunner()


def test_requeue_by_lead_id():
    store = MemoryStore()
    lead = load_json_leads(SAMPLE_QUEUE)[0]
    lead.status = LeadStatus.APPROVED_FOR_SCOUT
    store.upsert_lead(lead)
    reset = requeue_leads(store, lead_ids=[lead.lead_id])
    assert len(reset) == 1
    assert store.get_lead(lead.lead_id).status == LeadStatus.QUEUED


def test_requeue_by_company_substring():
    store = MemoryStore()
    for lead in load_json_leads(SAMPLE_QUEUE):
        lead.status = LeadStatus.DRAFTED
        store.upsert_lead(lead)
    reset = requeue_leads(store, company="harbor")
    assert len(reset) == 1
    assert reset[0].company == "Harbor Regional Bank"
    assert store.get_lead(reset[0].lead_id).status == LeadStatus.QUEUED


def test_requeue_all_sample_upserts_queued():
    store = MemoryStore()
    reset = requeue_leads(store, all_sample=True)
    assert len(reset) == 3
    assert {lead.company for lead in reset} == {
        "Northline Manufacturing",
        "Harbor Regional Bank",
        "Orbit Ledger SaaS",
    }
    assert all(lead.status == LeadStatus.QUEUED for lead in store.list_leads())


def test_requeue_clear_processing():
    store = MemoryStore()
    leads = load_json_leads(SAMPLE_QUEUE)
    leads[0].status = LeadStatus.PROCESSING
    leads[1].status = LeadStatus.APPROVED_FOR_SCOUT
    store.upsert_lead(leads[0])
    store.upsert_lead(leads[1])
    reset = requeue_leads(store, clear_processing=True)
    assert [lead.lead_id for lead in reset] == [leads[0].lead_id]
    assert store.get_lead(leads[0].lead_id).status == LeadStatus.QUEUED
    assert store.get_lead(leads[1].lead_id).status == LeadStatus.APPROVED_FOR_SCOUT


def test_requeue_persists_work_queue(tmp_path: Path):
    work = tmp_path / "leads.work.json"
    leads = [lead.model_dump(mode="json") for lead in load_json_leads(SAMPLE_QUEUE)]
    leads[0]["status"] = "approved_for_scout"
    work.write_text(json.dumps({"leads": leads}), encoding="utf-8")
    store = MemoryStore()
    queue = JsonLeadQueue(store, work)
    requeue_leads(store, lead_ids=[leads[0]["lead_id"]])
    queue.persist()
    restored = load_json_leads(work)
    northline = next(lead for lead in restored if lead.lead_id == leads[0]["lead_id"])
    assert northline.status == LeadStatus.QUEUED


def test_cli_requeue_all_sample():
    result = runner.invoke(app, ["requeue", "--all-sample"])
    assert result.exit_code == 0, result.stdout
    assert "Northline Manufacturing" in result.stdout
    assert "queued" in result.stdout
    assert "11111111-1111-1111-1111-111111111111" in result.stdout


def test_parse_requeue_status_aliases():
    assert parse_requeue_status("processing") == {LeadStatus.PROCESSING}
    assert parse_requeue_status("failed") == {LeadStatus.FAILED}
    assert LeadStatus.APPROVED_FOR_SCOUT in parse_requeue_status("done")
    assert LeadStatus.DRAFTED in parse_requeue_status("done")


def test_requeue_by_status_failed_and_done():
    store = MemoryStore()
    failed = Lead(company="Fail Co", status=LeadStatus.FAILED)
    done = Lead(company="Done Co", status=LeadStatus.APPROVED_FOR_SCOUT)
    store.upsert_lead(failed)
    store.upsert_lead(done)
    reset = requeue_leads(store, statuses=parse_requeue_status("failed"))
    assert {lead.lead_id for lead in reset} == {failed.lead_id}
    assert store.get_lead(failed.lead_id).status == LeadStatus.QUEUED
    done_batch = requeue_leads(store, statuses=parse_requeue_status("done"))
    assert {lead.lead_id for lead in done_batch} == {done.lead_id}
    assert store.get_lead(done.lead_id).status == LeadStatus.QUEUED


def test_cli_requeue_status_processing():
    result = runner.invoke(app, ["requeue", "--status", "processing"])
    assert result.exit_code == 0, result.stdout
    assert "requeued" in result.stdout.lower() or "queued" in result.stdout


def test_swarm_requeue_then_claim_stuck_leads():
    settings = Settings(mock_mode=True, simulate_outcomes=True)
    store = MemoryStore()
    for lead in load_json_leads(SAMPLE_QUEUE):
        lead.status = LeadStatus.PROCESSING
        store.upsert_lead(lead)
    requeued = requeue_leads(store, statuses={LeadStatus.PROCESSING, LeadStatus.FAILED})
    assert len(requeued) == 3
    swarm = build_swarm(settings, concurrency=2, store=store)
    report = swarm.run_once()
    assert report.processed == 3
    assert report.succeeded == 3


def test_cli_queue_reset_by_lead_id():
    result = runner.invoke(
        app,
        ["queue", "reset", "--lead-id", "11111111-1111-1111-1111-111111111111"],
    )
    assert result.exit_code == 0, result.stdout
    assert "11111111-1111-1111-1111-111111111111" in result.stdout
