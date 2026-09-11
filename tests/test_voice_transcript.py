import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from self_improving_outreach.cli import app
from self_improving_outreach.config import Settings
from self_improving_outreach.crews.pipeline import OutreachPipeline
from self_improving_outreach.observability.tracing import LoggingTracer
from self_improving_outreach.stores.memory import MemoryStore
from self_improving_outreach.swarm.queue import lead_from_mapping
from self_improving_outreach.tools.you_com import MockYouComClient, ResilientYouCom
from self_improving_outreach.voice.livekit_agent import record_voice_feedback
from self_improving_outreach.voice.transcript import (
    parse_voice_transcript,
    parse_voice_transcript_file,
    resolve_transcript_path,
)


def _cfo_lead():
    return lead_from_mapping(
        {
            "lead_id": "11111111-1111-1111-1111-111111111111",
            "company": "Northline Manufacturing",
            "contact_name": "Priya Shah",
            "title": "CFO",
            "industry": "manufacturing",
            "signals": {"pain": "SOX 404 material weakness"},
        }
    )


def test_parse_voice_transcript_positive_notes_and_pattern():
    feedback = parse_voice_transcript(
        {
            "lead_id": "11111111-1111-1111-1111-111111111111",
            "positive": True,
            "notes": "material-weakness angle landed",
            "pattern_id": "mw-90d",
            "transcript": "CFO liked the 90-day framing.",
        }
    )
    assert feedback.positive is True
    assert feedback.pattern_id == "mw-90d"
    assert "material-weakness" in feedback.notes
    assert "90-day" in feedback.notes
    assert feedback.lead_id == "11111111-1111-1111-1111-111111111111"


def test_parse_voice_transcript_negative_aliases():
    for payload in (
        {"sentiment": "negative", "notes": "too generic"},
        {"outcome": "thumbs_down", "pattern": "cfo-cio-copilot"},
        {"thumbs": "down"},
        {"feedback": {"positive": False, "notes": "pass"}},
    ):
        feedback = parse_voice_transcript(payload)
        assert feedback.positive is False


def test_parse_voice_transcript_requires_sentiment():
    with pytest.raises(ValueError, match="positive/negative"):
        parse_voice_transcript({"notes": "no polarity"})


def test_parse_voice_transcript_file(tmp_path: Path):
    path = tmp_path / "interview.json"
    path.write_text(
        json.dumps(
            {
                "lead_id": "11111111-1111-1111-1111-111111111111",
                "outcome": "thumbs_up",
                "pattern_id": "mw-90d",
                "notes": "from file",
            }
        ),
        encoding="utf-8",
    )
    feedback = parse_voice_transcript_file(path)
    assert feedback.positive is True
    assert feedback.pattern_id == "mw-90d"
    assert feedback.notes == "from file"


def test_record_voice_feedback_persists_livekit_source():
    store = MemoryStore()
    lead = _cfo_lead()
    store.upsert_lead(lead)
    before = store.get_weights()["cfo_cio_title"]
    record_voice_feedback(
        store,
        lead,
        positive=True,
        notes="AE preference interview",
        pattern_id="mw-90d",
        run_id="run-voice-1",
    )
    assert store.get_weights()["cfo_cio_title"] > before
    events = [event for event in store.events if event.metadata.get("source") == "livekit"]
    assert len(events) == 1
    assert events[0].channel.value == "voice"
    assert events[0].outcome.value == "thumbs_up"
    assert events[0].metadata["source"] == "livekit"
    assert events[0].metadata["positive"] is True
    assert events[0].pattern_id == "mw-90d"


def test_pipeline_auto_hook_reads_transcript(tmp_path: Path):
    lead = _cfo_lead()
    transcript = tmp_path / f"{lead.lead_id}.json"
    transcript.write_text(
        json.dumps(
            {
                "lead_id": lead.lead_id,
                "positive": True,
                "pattern_id": "mw-90d",
                "notes": "auto hook",
            }
        ),
        encoding="utf-8",
    )
    settings = Settings(
        mock_mode=True,
        simulate_outcomes=False,
        livekit_feedback_auto=True,
        livekit_transcript_path=str(tmp_path),
    )
    store = MemoryStore()
    tracer = LoggingTracer()
    you = ResilientYouCom(MockYouComClient(), store, tracer)
    result = OutreachPipeline(settings, store, you, tracer).run(lead)
    assert result.ok
    assert result.learned is True
    voice_events = [event for event in store.events if event.metadata.get("source") == "livekit"]
    assert voice_events
    assert voice_events[0].metadata["auto"] is True
    assert voice_events[0].metadata["notes"] == "auto hook"


def test_resolve_transcript_path_file_and_directory(tmp_path: Path):
    lead_id = "11111111-1111-1111-1111-111111111111"
    directory = tmp_path / "voice"
    directory.mkdir()
    named = directory / f"{lead_id}.json"
    named.write_text("{}", encoding="utf-8")
    assert resolve_transcript_path(str(directory), lead_id) == named
    single = tmp_path / "one.json"
    single.write_text("{}", encoding="utf-8")
    assert resolve_transcript_path(str(single), lead_id) == single
    assert resolve_transcript_path(None, lead_id) is None


def test_cli_voice_transcript_file_without_livekit_keys():
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "voice",
            "--lead-id",
            "11111111-1111-1111-1111-111111111111",
            "--transcript-file",
            "data/voice_transcript.sample.json",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "LiveKit not configured" in result.stdout
    assert "livekit" in result.stdout.lower()
    assert "true" in result.stdout.lower()
