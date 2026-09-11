"""Optional LiveKit Agents voice follow-up / preference interview.

Core text crew does not import this module. Scaffold follows current LiveKit
Agents Python patterns (AgentServer + AgentSession, env LIVEKIT_URL /
LIVEKIT_API_KEY / LIVEKIT_API_SECRET).
"""

from __future__ import annotations

import logging
from typing import Optional

from self_improving_outreach.brand import BRAND, FOUNDER, POSITIONING
from self_improving_outreach.config import Settings
from self_improving_outreach.learning.learner import apply_learn_event
from self_improving_outreach.models import Lead, LearnEvent, Outcome
from self_improving_outreach.stores.base import OutreachStore

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
) -> dict[str, float]:
    """Called after a voice interview (or a mock transcript) to feed the Learner."""
    outcome = Outcome.THUMBS_UP if positive else Outcome.THUMBS_DOWN
    event = LearnEvent(
        lead_id=lead.lead_id,
        outcome=outcome,
        pattern_id=pattern_id,
        notes=notes or "livekit_voice_interview",
    )
    return apply_learn_event(store, event, lead)


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
