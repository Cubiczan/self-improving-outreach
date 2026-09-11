from typer.testing import CliRunner

from self_improving_outreach.cli import app
from self_improving_outreach.config import Settings
from self_improving_outreach.crews.pipeline import OutreachPipeline
from self_improving_outreach.learning.defaults import DEFAULT_WEIGHTS
from self_improving_outreach.models import Outcome
from self_improving_outreach.observability.tracing import LoggingTracer
from self_improving_outreach.stores.memory import MemoryStore
from self_improving_outreach.swarm.queue import lead_from_mapping
from self_improving_outreach.tools.you_com import MockYouComClient, ResilientYouCom

runner = CliRunner()


def _cfo_lead():
    return lead_from_mapping(
        {
            "lead_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "company": "Northline Manufacturing",
            "contact_name": "Priya Shah",
            "title": "CFO",
            "industry": "manufacturing",
            "signals": {"pain": "SOX 404 material weakness", "employees": 1200},
        }
    )


def _pipeline(settings: Settings, store: MemoryStore | None = None) -> tuple[OutreachPipeline, MemoryStore]:
    store = store or MemoryStore()
    tracer = LoggingTracer()
    you = ResilientYouCom(MockYouComClient(), store, tracer)
    return OutreachPipeline(settings, store, you, tracer), store


def test_learn_on_draft_live_updates_weights_and_patterns():
    settings = Settings(mock_mode=False, learn_on_draft=True, simulate_outcomes=False)
    pipeline, store = _pipeline(settings)
    before = store.get_weights()["cfo_cio_title"]
    result = pipeline.run(_cfo_lead())
    assert result.ok
    assert result.learned is True
    assert store.get_weights()["cfo_cio_title"] > before
    assert store.get_weights()["material_weakness_or_sox"] > DEFAULT_WEIGHTS["material_weakness_or_sox"]
    pattern = next(p for p in store.list_patterns() if p.pattern_id == result.draft.pattern_id)
    assert pattern.impressions >= 1
    assert any(event.outcome != Outcome.DRAFTED for event in store.events)


def test_live_path_does_not_simulate_without_learn_on_draft():
    settings = Settings(mock_mode=False, learn_on_draft=False, simulate_outcomes=True)
    assert settings.should_learn_on_draft is False
    pipeline, store = _pipeline(settings)
    before = dict(store.get_weights())
    result = pipeline.run(_cfo_lead())
    assert result.ok
    assert result.learned is False
    assert store.get_weights() == before
    assert all(event.outcome == Outcome.DRAFTED for event in store.events)


def test_mock_simulate_still_learns():
    settings = Settings(mock_mode=True, learn_on_draft=False, simulate_outcomes=True)
    assert settings.should_learn_on_draft is True
    pipeline, store = _pipeline(settings)
    result = pipeline.run(_cfo_lead())
    assert result.ok
    assert result.learned is True


def test_cli_learn_meeting_updates_sample_lead():
    result = runner.invoke(
        app,
        [
            "learn",
            "--event",
            '{"lead_id":"11111111-1111-1111-1111-111111111111","outcome":"meeting","pattern_id":"mw-90d"}',
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "meeting" in result.stdout
    assert "mw-90d" in result.stdout
    assert "cfo_cio_title" in result.stdout
