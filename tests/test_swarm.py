from pathlib import Path

from self_improving_outreach.config import Settings
from self_improving_outreach.crews.pipeline import OutreachPipeline, critique_draft
from self_improving_outreach.models import Channel, Draft, LeadStatus
from self_improving_outreach.observability.tracing import LoggingTracer
from self_improving_outreach.runtime import SAMPLE_QUEUE, build_swarm
from self_improving_outreach.stores.memory import MemoryStore
from self_improving_outreach.swarm.queue import JsonLeadQueue, load_json_leads
from self_improving_outreach.tools.you_com import MockYouComClient, ResilientYouCom


def test_sample_queue_has_three_leads():
    leads = load_json_leads(SAMPLE_QUEUE)
    assert len(leads) == 3


def test_mock_swarm_once_processes_three_leads_without_keys():
    settings = Settings(mock_mode=True, simulate_outcomes=True)
    store = MemoryStore()
    swarm = build_swarm(settings, concurrency=2, queue_path=str(SAMPLE_QUEUE), store=store)
    report = swarm.run_once()
    assert report.processed == 3
    assert report.succeeded == 3
    assert report.failed == 0
    assert len(store.list_patterns()) >= 5
    assert store.events  # drafts + simulated outcomes


def test_worker_youcom_failure_does_not_kill_swarm():
    settings = Settings(mock_mode=True, simulate_outcomes=True)
    store = MemoryStore()
    client = MockYouComClient(fail_on_query="Harbor Regional Bank")
    swarm = build_swarm(
        settings,
        concurrency=3,
        queue_path=str(SAMPLE_QUEUE),
        you_client=client,
        store=store,
    )
    report = swarm.run_once()
    assert report.processed == 3
    assert report.succeeded == 3
    assert report.degraded >= 1
    assert store.list_tool_failures()
    companies = {result.lead.company for result in report.results}
    assert companies == {
        "Northline Manufacturing",
        "Harbor Regional Bank",
        "Orbit Ledger SaaS",
    }


def test_next_batch_prefers_winning_pattern():
    settings = Settings(mock_mode=True, simulate_outcomes=True)
    store = MemoryStore()
    swarm = build_swarm(settings, concurrency=1, queue_path=str(SAMPLE_QUEUE), store=store)
    first = swarm.run_once(max_leads=3)
    assert first.succeeded == 3
    winner = store.list_patterns()[0]

    extra = load_json_leads(SAMPLE_QUEUE)[0]
    extra.lead_id = "44444444-4444-4444-4444-444444444444"
    extra.company = "Second-batch Industrials"
    extra.status = extra.status.__class__("queued")
    store.upsert_lead(extra)
    second = swarm.run_once(max_leads=1)
    assert second.succeeded == 1
    drafted = second.results[0].draft
    assert drafted is not None
    assert drafted.pattern_id == winner.pattern_id


def test_critic_rewrites_brand_misspelling():
    draft = Draft(
        pattern_id="mw-90d",
        angle="90-day material-weakness remediation",
        body="Hi there from CubicZan — we guarantee close automation.",
        channel=Channel.LINKEDIN,
    )
    critique = critique_draft(draft)
    assert "CubicZan" not in (critique.revised_body or "")
    assert "Cubiczan" in (critique.revised_body or "")


def test_human_gate_stub_holds_draft(tmp_path: Path):
    settings = Settings(
        mock_mode=True,
        human_gate_enabled=True,
        pending_approvals_path=str(tmp_path / "pending.jsonl"),
        simulate_outcomes=False,
    )
    store = MemoryStore()
    leads = load_json_leads(SAMPLE_QUEUE)
    store.upsert_lead(leads[0])
    tracer = LoggingTracer()
    you = ResilientYouCom(MockYouComClient(), store, tracer)
    result = OutreachPipeline(settings, store, you, tracer).run(leads[0])
    assert result.gate is not None
    assert result.gate.status == LeadStatus.PENDING_REVIEW
    assert (tmp_path / "pending.jsonl").read_text(encoding="utf-8")
