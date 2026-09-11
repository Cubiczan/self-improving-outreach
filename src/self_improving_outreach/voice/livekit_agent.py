"""Optional LiveKit Agents voice follow-up / preference interview.

Core text crew does not import this module at import time. Scaffold follows
current LiveKit Agents Python patterns (AgentServer + AgentSession, env
LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET). Mock interview and
transcript-file ingest work without LiveKit keys.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from self_improving_outreach.brand import BRAND, FOUNDER, POSITIONING
from self_improving_outreach.config import Settings
from self_improving_outreach.learning.learner import apply_learn_event
from self_improving_outreach.models import Channel, Lead, LearnEvent, Outcome, OutreachEvent, new_id
from self_improving_outreach.paths import sample_voice_transcript_path
from self_improving_outreach.stores.base import OutreachStore
from self_improving_outreach.voice.transcript import (
    VoiceTranscriptFeedback,
    parse_voice_transcript_file,
    resolve_transcript_path,
)

STUB_NOTES = (
    "LIVEKIT_FEEDBACK_AUTO stub: preference interview enqueued "
    "(async AgentSession). Sample transcript applied so the Learner path runs. "
    "Replace with a real AE interview or LIVEKIT_TRANSCRIPT_PATH."
)

logger = logging.getLogger(__name__)

INSTRUCTIONS = f"""You are a {BRAND} voice agent working for {FOUNDER}.
You interview a prospect or an internal AE about which outreach angle landed.
Positioning: {POSITIONING}.
Ask what messaging, ICP, or pain (close, recon, treasury, material weakness)
resonated. Summarize preferences so the Learner can update ClickHouse weights.
You do not send LinkedIn messages. Pipeline Scout owns send.
"""


def livekit_configured(settings: Settings) -> bool:
    return bool(settings.livekit_api_key and settings.livekit_api_secret and settings.livekit_url)


def livekit_available() -> bool:
    try:
        import livekit.agents  # noqa: F401

        return True
    except Exception:
        return False


def record_voice_feedback(
    store: OutreachStore,
    lead: Lead,
    *,
    positive: bool,
    notes: str = "",
    pattern_id: Optional[str] = None,
    run_id: Optional[str] = None,
    auto: bool = False,
    stub: bool = False,
) -> dict[str, float]:
    """Called after a voice interview (or a mock transcript) to feed the Learner."""
    outcome = Outcome.THUMBS_UP if positive else Outcome.THUMBS_DOWN
    latest = store.latest_event(lead.lead_id)
    resolved_pattern = pattern_id or (latest.pattern_id if latest else None)
    resolved_run = run_id or (latest.run_id if latest else new_id())
    resolved_angle = latest.angle if latest else ""
    event = LearnEvent(
        lead_id=lead.lead_id,
        outcome=outcome,
        run_id=resolved_run,
        pattern_id=resolved_pattern,
        angle=resolved_angle or None,
        notes=notes or "livekit_voice_interview",
    )
    weights = apply_learn_event(store, event, lead)
    store.log_event(
        OutreachEvent(
            lead_id=lead.lead_id,
            run_id=resolved_run,
            channel=Channel.VOICE,
            outcome=outcome,
            angle=resolved_angle,
            pattern_id=resolved_pattern or "",
            body=notes or "livekit_voice_interview",
            metadata={
                "source": "livekit",
                "positive": positive,
                "notes": notes or "livekit_voice_interview",
                "auto": auto,
                "stub": stub,
            },
        )
    )
    return weights


def record_transcript_feedback(
    store: OutreachStore,
    lead: Lead,
    feedback: VoiceTranscriptFeedback,
    *,
    run_id: Optional[str] = None,
    auto: bool = False,
    stub: bool = False,
) -> dict[str, float]:
    return record_voice_feedback(
        store,
        lead,
        positive=feedback.positive,
        notes=feedback.notes,
        pattern_id=feedback.pattern_id,
        run_id=run_id,
        auto=auto,
        stub=stub,
    )


def maybe_apply_auto_voice_feedback(
    settings: Settings,
    store: OutreachStore,
    lead: Lead,
    *,
    run_id: Optional[str] = None,
    pattern_id: Optional[str] = None,
    transcript_path: Optional[Path | str] = None,
) -> bool:
    """After a successful draft, optionally ingest a JSON transcript into the Learner."""
    if not settings.livekit_feedback_auto:
        return False
    path = resolve_transcript_path(
        settings.livekit_transcript_path,
        lead.lead_id,
        override=transcript_path,
    )
    if path is not None:
        try:
            feedback = parse_voice_transcript_file(path)
        except ValueError as exc:
            logger.warning("Skipping auto voice transcript %s: %s", path, exc)
            return False
        if feedback.lead_id and feedback.lead_id != lead.lead_id:
            logger.warning(
                "Transcript lead_id %s does not match pipeline lead %s; skipping",
                feedback.lead_id,
                lead.lead_id,
            )
            return False
        if not feedback.pattern_id and pattern_id:
            feedback = feedback.model_copy(update={"pattern_id": pattern_id})
        record_transcript_feedback(store, lead, feedback, run_id=run_id, auto=True)
        return True
    if livekit_configured(settings):
        logger.info(
            "LIVEKIT_FEEDBACK_AUTO: no transcript for %s; running preference-interview stub",
            lead.lead_id,
        )
        enqueue_preference_interview_stub(
            store,
            lead,
            run_id=run_id,
            pattern_id=pattern_id,
        )
        return True
    logger.info("LIVEKIT_FEEDBACK_AUTO set but no transcript found for %s", lead.lead_id)
    return False


def enqueue_preference_interview_stub(
    store: OutreachStore,
    lead: Lead,
    *,
    run_id: Optional[str] = None,
    pattern_id: Optional[str] = None,
) -> dict[str, float]:
    """Documented stub: full AgentSession is async. Apply a sample transcript to the Learner."""
    feedback = _sample_stub_feedback(lead, pattern_id)
    return record_transcript_feedback(
        store,
        lead,
        feedback,
        run_id=run_id,
        auto=True,
        stub=True,
    )


def _sample_stub_feedback(
    lead: Lead,
    pattern_id: Optional[str],
) -> VoiceTranscriptFeedback:
    sample = sample_voice_transcript_path()
    if sample.is_file():
        try:
            feedback = parse_voice_transcript_file(sample)
            updates: dict = {"lead_id": lead.lead_id, "notes": STUB_NOTES}
            if pattern_id:
                updates["pattern_id"] = pattern_id
            return feedback.model_copy(update=updates)
        except ValueError as exc:
            logger.warning("Sample voice transcript unreadable (%s); using inline stub", exc)
    return VoiceTranscriptFeedback(
        positive=True,
        notes=STUB_NOTES,
        pattern_id=pattern_id,
        lead_id=lead.lead_id,
    )


def build_agent_server(settings: Settings):
    """Return a LiveKit AgentServer entrypoint, or raise if the extra is missing."""
    if not livekit_available():
        raise RuntimeError("livekit-agents is not installed. uv sync --extra livekit")
    if not livekit_configured(settings):
        raise RuntimeError("Set LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET")

    from livekit.agents import Agent, AgentServer, AgentSession, JobContext

    server = AgentServer()

    @server.rtc_session(agent_name="cubiczan-preference-interview")
    async def entrypoint(ctx: JobContext) -> None:
        session = AgentSession(
            stt="deepgram/nova-3",
            llm="openai/gpt-4o-mini",
            tts="cartesia/sonic-3",
        )
        await session.start(
            room=ctx.room,
            agent=Agent(instructions=INSTRUCTIONS),
        )

    return server


def describe_status(settings: Settings) -> str:
    if not livekit_configured(settings):
        return "LiveKit not configured; voice module idle (text crew still runs)."
    if not livekit_available():
        return "LiveKit keys present but livekit-agents extra is not installed."
    return "LiveKit configured. Run: python -m self_improving_outreach voice --help"
