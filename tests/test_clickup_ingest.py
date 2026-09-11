import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from self_improving_outreach.cli import app
from self_improving_outreach.integrations.clickup import ingest_clickup_payload, lead_from_clickup
from self_improving_outreach.models import LeadStatus
from self_improving_outreach.stores.memory import MemoryStore
from self_improving_outreach.swarm.queue import load_json_leads

runner = CliRunner()

SAMPLE_CLICKUP = Path("data/clickup_task.sample.json")


def test_lead_from_clickup_webhook_queued():
    payload = json.loads(SAMPLE_CLICKUP.read_text(encoding="utf-8"))
    result = lead_from_clickup(payload)
    assert result.skipped is False
    assert result.lead is not None
    assert result.lead.status == LeadStatus.QUEUED
    assert result.lead.lead_id == "clickup-86abcqueued"
    assert result.lead.company == "Northline Manufacturing"
    assert result.lead.contact_name == "Priya Shah"
    assert result.lead.title == "CFO"
    assert result.lead.industry == "manufacturing"
    assert result.lead.domain == "northline.example"
    assert result.lead.signals["clickup_task_id"] == "86abcqueued"
    assert result.lead.signals["pain"] == "SOX 404 material weakness"


def test_lead_from_clickup_skips_non_queued():
    result = lead_from_clickup(
        {
            "id": "task-busy",
            "name": "Harbor Regional Bank — Marcus Lee",
            "status": {"status": "in progress"},
        }
    )
    assert result.skipped is True
    assert result.lead is None
    assert "not Queued" in result.reason


def test_lead_from_clickup_force_non_queued():
    result = lead_from_clickup(
        {
            "id": "task-busy",
            "name": "Harbor Regional Bank — Marcus Lee",
            "status": "in progress",
            "title": "CIO",
        },
        force=True,
    )
    assert result.skipped is False
    assert result.lead is not None
    assert result.lead.company == "Harbor Regional Bank"
    assert result.lead.status == LeadStatus.QUEUED


def test_ingest_clickup_writes_store():
    store = MemoryStore()
    payload = json.loads(SAMPLE_CLICKUP.read_text(encoding="utf-8"))
    result = ingest_clickup_payload(store, payload)
    stored = store.get_lead("clickup-86abcqueued")
    assert result.lead is not None
    assert stored is not None
    assert stored.status == LeadStatus.QUEUED
    assert stored.company == "Northline Manufacturing"


def test_cli_ingest_clickup_sample_file():
    result = runner.invoke(app, ["ingest-clickup", "--file", str(SAMPLE_CLICKUP)])
    assert result.exit_code == 0, result.stdout
    assert "clickup-86abcqueued" in result.stdout
    assert "Northline Manufacturing" in result.stdout
    assert "queued" in result.stdout


def test_cli_ingest_clickup_skips_non_queued():
    result = runner.invoke(
        app,
        [
            "ingest-clickup",
            "--json",
            json.dumps({"id": "x", "name": "Acme", "status": {"status": "to do"}}),
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "skipped" in result.stdout


def test_cli_queue_upsert_from_json(tmp_path: Path):
    work = tmp_path / "leads.work.json"
    payload = {
        "company": "Second-batch Industrials",
        "contact_name": "Ada",
        "title": "CFO",
        "lead_id": "44444444-4444-4444-4444-444444444444",
        "status": "approved_for_scout",
    }
    result = runner.invoke(
        app,
        ["queue", "upsert", "--from-json", json.dumps(payload), "--queue", str(work)],
    )
    assert result.exit_code == 0, result.stdout
    leads = load_json_leads(work)
    assert len(leads) == 1
    assert leads[0].status == LeadStatus.QUEUED
    assert leads[0].company == "Second-batch Industrials"


def test_clickup_requires_company():
    with pytest.raises(ValueError, match="company"):
        lead_from_clickup({"id": "empty", "status": "Queued"})
