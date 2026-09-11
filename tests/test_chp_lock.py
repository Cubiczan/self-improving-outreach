"""CHP decision lock: R0, non-skippable adversary, named lock, evidence pack."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from self_improving_outreach.chp.adversary import run_structural_adversary
from self_improving_outreach.chp.exceptions import (
    AdversaryRequiredError,
    EvidencePackError,
    ImmutableCommitError,
    NamedActorRequired,
)
from self_improving_outreach.chp.hashing import canonical_digest
from self_improving_outreach.chp.models import ChpPhase
from self_improving_outreach.chp.r0 import PEER_FIELDS, commit_r0, verify_r0
from self_improving_outreach.chp.session import (
    apply_named_lock,
    promote_to_scout,
    start_chp_session,
    verify_evidence_pack,
)
from self_improving_outreach.cli import app
from self_improving_outreach.config import Settings, public_settings_view
from self_improving_outreach.crews.pipeline import OutreachPipeline
from self_improving_outreach.learning.scorer import score_lead
from self_improving_outreach.models import (
    Channel,
    Draft,
    Lead,
    LeadStatus,
    ResearchBundle,
    ScoreResult,
)
from self_improving_outreach.observability.tracing import LoggingTracer
from self_improving_outreach.runtime import build_you_client
from self_improving_outreach.stores.memory import MemoryStore
from self_improving_outreach.swarm.queue import lead_from_mapping
from self_improving_outreach.tools.you_com import ResilientYouCom


def _lead() -> Lead:
    return lead_from_mapping(
        {
            "company": "Northline Manufacturing",
            "contact_name": "Priya Shah",
            "title": "CFO",
            "industry": "manufacturing",
            "signals": {"pain": "material weakness"},
        }
    )


def _unit(store: MemoryStore | None = None) -> tuple[Lead, ResearchBundle, ScoreResult, Draft]:
    store = store or MemoryStore()
    lead = _lead()
    store.upsert_lead(lead)
    research = ResearchBundle(
        query="Northline",
        synthesis="Cached CFO context",
        source="mock",
        degraded=False,
    )
    score = score_lead(lead, store, research)
    draft = Draft(
        channel=Channel.LINKEDIN,
        pattern_id="mw-90d",
        angle="90-day material-weakness remediation",
        subject="Cubiczan × Northline",
        body="Hi Priya — Sam Desigan at Cubiczan on 90-day material-weakness work.",
    )
    return lead, research, score, draft


def test_chp_flag_defaults_true_on_live_false_on_mock():
    mock = Settings(mock_mode=True)
    assert mock.resolved_chp_lock_enabled is False
    live = Settings(
        mock_mode=False,
        openai_api_key="sk-test",
        you_api_key="ydc",
        one_cli_auth=False,
    )
    assert live.is_mock is False
    assert live.resolved_chp_lock_enabled is True
    forced = Settings(mock_mode=True, chp_lock_enabled=True)
    assert forced.resolved_chp_lock_enabled is True
    off = Settings(
        mock_mode=False,
        openai_api_key="sk-test",
        you_api_key="ydc",
        chp_lock_enabled=False,
        one_cli_auth=False,
    )
    assert off.resolved_chp_lock_enabled is False


def test_public_settings_includes_chp_flag_not_secrets():
    settings = Settings(mock_mode=True, boundless_api_key="sk-secret-boundless")
    view = public_settings_view(settings)
    assert view["chp_lock_enabled"] is False
    assert "sk-secret-boundless" not in str(view)


def test_r0_peer_seals_are_independent_and_immutable():
    lead, research, score, draft = _unit()
    r0 = commit_r0(lead, research, score, draft, run_id="run-1")
    verify_r0(r0)
    assert set(r0.peers) == {"research", "score", "draft"}
    assert "body" not in r0.peers["research"].payload
    assert "body" not in r0.peers["score"].payload
    assert "total" not in r0.peers["research"].payload
    assert "synthesis" not in r0.peers["draft"].payload
    assert set(r0.peers["research"].payload) == set(PEER_FIELDS["research"])
    assert set(r0.peers["score"].payload) == set(PEER_FIELDS["score"])
    assert r0.gate.verdict == "PASS"
    r0.peers["draft"].payload["body"] = "tampered"
    with pytest.raises(ImmutableCommitError):
        verify_r0(r0)


def test_structural_adversary_is_not_skippable_and_binds_r0():
    lead, research, score, draft = _unit()
    session = start_chp_session(lead, research, score, draft, run_id="run-2")
    assert session.phase == ChpPhase.PROVISIONAL
    assert session.adversary is not None
    assert session.adversary.skippable is False
    assert session.adversary.r0_digest == session.r0.digest
    with pytest.raises(AdversaryRequiredError):
        start_chp_session(lead, research, score, draft, run_id="run-2b", skip_adversary=True)
    with pytest.raises(AdversaryRequiredError):
        run_structural_adversary(session.r0, draft, research, skip=True)


def test_adversary_flags_send_implication_and_brand():
    lead, research, score, draft = _unit()
    draft.body = "Hi from CubicZan — we already sent this on LinkedIn, guaranteed."
    r0 = commit_r0(lead, research, score, draft, run_id="run-3")
    report = run_structural_adversary(
        r0, draft, research, crewai_notes=["pr9 extra"]
    )
    assert "brand misspelling" in report.findings
    assert "send implication" in report.findings
    assert "overclaim" in report.findings
    assert report.crewai_adversary_notes == ["pr9 extra"]
    assert report.r0_digest == r0.digest
    assert report.skippable is False


def test_named_lock_approve_seals_pack_and_promotes():
    lead, research, score, draft = _unit()
    decision = start_chp_session(lead, research, score, draft, run_id="run-4")
    with pytest.raises(NamedActorRequired):
        apply_named_lock(decision, actor="auto", approve=True)
    with pytest.raises(NamedActorRequired):
        apply_named_lock(decision, actor="  ", approve=True)
    apply_named_lock(decision, actor="Sam Desigan", approve=True, notes="ok")
    assert decision.phase == ChpPhase.LOCKED
    assert decision.lock is not None
    assert decision.lock.actor == "Sam Desigan"
    pack = verify_evidence_pack(decision)
    assert pack.r0_digest == decision.r0.digest
    assert pack.adversary_digest == decision.adversary.digest
    assert pack.lock_digest == decision.lock.digest
    assert pack.pack_digest == canonical_digest(
        {
            "adversary": decision.adversary.digest,
            "lock": decision.lock.digest,
            "r0": decision.r0.digest,
        }
    )
    with pytest.raises(Exception):
        decision.evidence_pack.r0_digest = "nope"  # type: ignore[misc]
    assert promote_to_scout(decision) == LeadStatus.APPROVED_FOR_SCOUT


def test_named_deny_does_not_approve_for_scout():
    lead, research, score, draft = _unit()
    decision = start_chp_session(lead, research, score, draft, run_id="run-5")
    apply_named_lock(decision, actor="Shyam Desigan", approve=False, notes="rewrite")
    assert decision.phase == ChpPhase.PROVISIONAL
    assert decision.evidence_pack is None
    with pytest.raises(EvidencePackError):
        promote_to_scout(decision)


def test_pipeline_holds_provisional_when_chp_on(tmp_path: Path):
    settings = Settings(
        mock_mode=True,
        chp_lock_enabled=True,
        chp_decisions_path=str(tmp_path / "chp.jsonl"),
        simulate_outcomes=False,
        one_cli_auth=False,
    )
    store = MemoryStore()
    you = ResilientYouCom(build_you_client(settings), store, LoggingTracer())
    pipeline = OutreachPipeline(settings, store, you, LoggingTracer())
    result = pipeline.run(_lead())
    assert result.ok
    assert result.gate is not None
    assert result.gate.status == LeadStatus.PROVISIONAL
    assert result.lead.status == LeadStatus.PROVISIONAL
    assert result.chp is not None
    assert result.chp.phase == ChpPhase.PROVISIONAL
    assert result.event is not None
    assert result.event.metadata["chp_phase"] == "provisional"
    assert result.event.metadata["gate"] == "provisional"
    stored = store.get_chp_decision(result.lead.lead_id)
    assert stored is not None
    assert stored.r0 is not None
    apply_named_lock(stored, actor="Sam Desigan", approve=True)
    assert promote_to_scout(stored) == LeadStatus.APPROVED_FOR_SCOUT


def test_score_remains_deterministic_under_chp():
    store = MemoryStore()
    lead, research, _, _ = _unit(store)
    first = score_lead(lead, store, research)
    second = score_lead(lead, store, research)
    assert first.total == second.total
    assert first.features == second.features
    assert first.weights == second.weights


def test_cli_chp_lock_flow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHP_LOCK_ENABLED", "true")
    monkeypatch.setenv("CHP_DECISIONS_PATH", str(tmp_path / "decisions.jsonl"))
    monkeypatch.setenv("SIMULATE_OUTCOMES", "false")
    from self_improving_outreach.config import reset_settings_cache

    reset_settings_cache()
    runner = CliRunner()
    run = runner.invoke(
        app,
        [
            "run",
            "--lead",
            '{"company":"Northline Manufacturing","title":"CFO","contact_name":"Priya","industry":"manufacturing"}',
        ],
    )
    assert run.exit_code == 0, run.stdout
    assert "provisional" in run.stdout
    import json as json_lib

    payload = json_lib.loads(run.stdout[run.stdout.find("{") :])
    assert payload["lead"]["status"] == "provisional"
    assert payload["gate"]["status"] == "provisional"
    lead_id = payload["lead"]["lead_id"]
    denied = runner.invoke(
        app,
        ["chp", "lock", "--lead-id", lead_id, "--deny", "--actor", "auto"],
    )
    assert denied.exit_code != 0
    locked = runner.invoke(
        app,
        ["chp", "lock", "--lead-id", lead_id, "--approve", "--actor", "Sam Desigan"],
    )
    assert locked.exit_code == 0, locked.stdout
    assert "locked" in locked.stdout
    assert "approved_for_scout" in locked.stdout
    assert '"send": false' in locked.stdout or "'send': False" in locked.stdout
