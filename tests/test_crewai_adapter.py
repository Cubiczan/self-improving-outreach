"""CrewAI utilization: plan/tools without a live LLM; mocked kickoff; fallback."""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import pytest

from self_improving_outreach.chp.models import ChpPhase
from self_improving_outreach.config import Settings
from self_improving_outreach.crews.crewai_adapter import (
    CREWAI_ADVERSARY_NOTE,
    TOOL_MEMORY,
    TOOL_YOU,
    adversary_prompt_suffix,
    build_crew_plan,
    optional_chp_foundation_floor,
    run_crewai_draft,
)
from self_improving_outreach.crews.pipeline import OutreachPipeline
from self_improving_outreach.models import Channel, Lead, LeadStatus, ResearchBundle, ScoreResult
from self_improving_outreach.observability.tracing import LoggingTracer
from self_improving_outreach.stores.memory import MemoryStore
from self_improving_outreach.tools.you_com import MockYouComClient, ResilientYouCom


def _lead() -> Lead:
    return Lead(
        company="Northline Manufacturing",
        contact_name="Priya Shah",
        title="VP Sales",
        industry="manufacturing",
    )


def _score() -> ScoreResult:
    return ScoreResult(total=42.0, features={"industry_fit": 1.0}, weights={"industry_fit": 0.7})


def _research() -> ResearchBundle:
    return ResearchBundle(query="northline", synthesis="Prefetched company brief.", source="mock")


def _live_settings(**kwargs) -> Settings:
    defaults = {"mock_mode": False, "openai_api_key": "sk-test", "you_api_key": "you-test"}
    defaults.update(kwargs)
    return Settings(**defaults)


def test_full_plan_attaches_you_tool_and_strategist():
    plan = build_crew_plan(
        _live_settings(crewai_mode="full"),
        _lead(),
        _research(),
        _score(),
        MemoryStore(),
        Channel.LINKEDIN,
    )
    assert plan.mode == "full"
    assert TOOL_YOU in plan.tool_names
    assert TOOL_MEMORY in plan.tool_names
    assert plan.agent("researcher").tool_names == (TOOL_YOU,)
    assert TOOL_YOU in plan.agent("strategist").tool_names
    assert TOOL_MEMORY in plan.agent("strategist").tool_names
    keys = [agent.key for agent in plan.agents]
    assert keys == ["researcher", "scorer", "strategist", "drafter", "critic"]
    assert "Adversary" in plan.agent("critic").role
    assert "CFO/CIO-only" not in plan.agent("researcher").goal
    assert "general outbound" in plan.agent("researcher").goal.lower()


def test_draft_plan_is_four_agents_without_tools():
    plan = build_crew_plan(
        _live_settings(crewai_mode="draft"),
        _lead(),
        _research(),
        _score(),
        MemoryStore(),
        Channel.EMAIL,
    )
    assert plan.mode == "draft"
    assert plan.tool_names == ()
    assert [agent.key for agent in plan.agents] == ["researcher", "scorer", "drafter", "critic"]
    assert all(agent.tool_names == () for agent in plan.agents)


def test_off_plan_is_empty():
    plan = build_crew_plan(
        Settings(mock_mode=True),
        _lead(),
        _research(),
        _score(),
        MemoryStore(),
        Channel.LINKEDIN,
    )
    assert plan.mode == "off"
    assert plan.agents == ()


def test_chp_missing_package_is_safe():
    assert optional_chp_foundation_floor() is None or isinstance(optional_chp_foundation_floor(), int)
    text = adversary_prompt_suffix()
    assert "adversary" in text.lower()
    assert "CHP" in text
    assert "harden prose only" in text
    assert "send-readiness" in text


def test_optional_floor_does_not_import_in_repo_chp_lock():
    """In-repo self_improving_outreach.chp is the lock, not a prompt floor."""
    import self_improving_outreach.chp as in_repo_chp  # noqa: F401

    assert optional_chp_foundation_floor() is None or isinstance(optional_chp_foundation_floor(), int)


@pytest.fixture
def fake_crewai(monkeypatch: pytest.MonkeyPatch):
    captured: dict = {"agents": [], "crews": [], "kickoff_error": None, "body": "Hardened outbound from Cubiczan."}

    class FakeBaseTool:
        pass

    class FakeAgent:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.role = kwargs.get("role")
            self.tools = kwargs.get("tools") or []
            captured["agents"].append(self)

    class FakeTask:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeCrew:
        def __init__(self, **kwargs):
            captured["crews"].append(kwargs)

        def kickoff(self):
            if captured["kickoff_error"]:
                raise captured["kickoff_error"]
            return SimpleNamespace(raw=captured["body"])

    class FakeProcess:
        sequential = "sequential"

    crewai_mod = types.ModuleType("crewai")
    crewai_mod.Agent = FakeAgent
    crewai_mod.Task = FakeTask
    crewai_mod.Crew = FakeCrew
    crewai_mod.Process = FakeProcess
    tools_mod = types.ModuleType("crewai.tools")
    tools_mod.BaseTool = FakeBaseTool
    monkeypatch.setitem(sys.modules, "crewai", crewai_mod)
    monkeypatch.setitem(sys.modules, "crewai.tools", tools_mod)
    return captured


def test_run_full_mode_attaches_you_tool_and_uses_kickoff_body(fake_crewai):
    tracer = LoggingTracer()
    store = MemoryStore()
    draft = run_crewai_draft(
        _live_settings(crewai_mode="full"),
        _lead(),
        _research(),
        _score(),
        store,
        Channel.LINKEDIN,
        tracer=tracer,
        you_refresh=lambda query: f"live:{query}",
    )
    assert draft is not None
    assert draft.body == "Hardened outbound from Cubiczan."
    assert draft.adversary_notes == [CREWAI_ADVERSARY_NOTE]
    researcher = next(agent for agent in fake_crewai["agents"] if agent.role == "Outbound Researcher")
    assert any(getattr(tool, "name", "") == TOOL_YOU for tool in researcher.tools)
    strategist = next(agent for agent in fake_crewai["agents"] if agent.role == "Outbound Strategist")
    tool_names = [getattr(tool, "name", "") for tool in strategist.tools]
    assert TOOL_YOU in tool_names
    assert TOOL_MEMORY in tool_names
    events = [row["name"] for row in tracer.records() if row.get("phase") == "event"]
    assert "crewai.mode" in events
    assert "crewai.tools" in events
    tool_events = [row for row in tracer.records() if row.get("name") == "crewai.tools"]
    assert tool_events[-1]["attributes"]["attached"] >= 1
    assert TOOL_YOU in tool_events[-1]["attributes"]["names"]


def test_run_draft_mode_has_no_tools(fake_crewai):
    draft = run_crewai_draft(
        _live_settings(crewai_mode="draft"),
        _lead(),
        _research(),
        _score(),
        MemoryStore(),
        Channel.LINKEDIN,
        you_refresh=lambda query: query,
    )
    assert draft is not None
    assert all(not agent.tools for agent in fake_crewai["agents"])


def test_kickoff_failure_falls_back_to_template(fake_crewai):
    fake_crewai["kickoff_error"] = RuntimeError("llm down")
    tracer = LoggingTracer()
    store = MemoryStore()
    lead = _lead()
    draft = run_crewai_draft(
        _live_settings(crewai_mode="full"),
        lead,
        _research(),
        _score(),
        store,
        Channel.LINKEDIN,
        tracer=tracer,
    )
    assert draft is not None
    assert "Cubiczan" in draft.body
    assert draft.body != "Hardened outbound from Cubiczan."
    assert any(row.get("name") == "crewai.fallback" for row in tracer.records())


def test_pipeline_emits_mode_and_falls_back_without_crewai_package(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "self_improving_outreach.crews.crewai_adapter.crewai_available",
        lambda: False,
    )
    settings = Settings(
        mock_mode=False,
        openai_api_key="sk-test",
        you_api_key="you-test",
        simulate_outcomes=False,
        one_cli_auth=False,
    )
    store = MemoryStore()
    tracer = LoggingTracer()
    you = ResilientYouCom(MockYouComClient(), store, tracer)
    result = OutreachPipeline(settings, store, you, tracer).run(_lead())
    assert result.ok
    assert result.draft is not None
    assert result.score.total > 0
    mode_events = [row for row in tracer.records() if row.get("name") == "crewai.mode"]
    assert mode_events
    assert mode_events[0]["attributes"]["mode"] == "full"
    assert any(row.get("name") == "crewai.fallback" for row in tracer.records())


def test_full_mode_does_not_bypass_chp_lock(fake_crewai, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "self_improving_outreach.crews.crewai_adapter.crewai_available",
        lambda: True,
    )
    settings = _live_settings(
        crewai_mode="full",
        chp_lock_enabled=True,
        chp_decisions_path=str(tmp_path / "chp.jsonl"),
        simulate_outcomes=False,
        one_cli_auth=False,
    )
    store = MemoryStore()
    tracer = LoggingTracer()
    you = ResilientYouCom(MockYouComClient(), store, tracer)
    result = OutreachPipeline(settings, store, you, tracer).run(_lead())
    assert result.ok
    assert result.draft is not None
    assert result.draft.body == "Hardened outbound from Cubiczan."
    assert result.draft.adversary_notes == [CREWAI_ADVERSARY_NOTE]
    assert result.lead.status == LeadStatus.PROVISIONAL
    assert result.gate is not None
    assert result.gate.status == LeadStatus.PROVISIONAL
    assert result.chp is not None
    assert result.chp.phase == ChpPhase.PROVISIONAL
    assert result.chp.adversary is not None
    assert result.chp.adversary.skippable is False
    assert CREWAI_ADVERSARY_NOTE in result.chp.adversary.crewai_adversary_notes
    assert result.lead.status != LeadStatus.APPROVED_FOR_SCOUT


def test_mock_pipeline_records_crewai_mode_off():
    settings = Settings(mock_mode=True, simulate_outcomes=False, one_cli_auth=False)
    store = MemoryStore()
    tracer = LoggingTracer()
    you = ResilientYouCom(MockYouComClient(), store, tracer)
    result = OutreachPipeline(settings, store, you, tracer).run(_lead())
    assert result.ok
    mode_events = [row for row in tracer.records() if row.get("name") == "crewai.mode"]
    assert mode_events
    assert mode_events[0]["attributes"]["mode"] == "off"
