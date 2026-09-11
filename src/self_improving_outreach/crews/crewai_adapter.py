"""CrewAI adapter. Optional — mock/deterministic pipeline does not import this at runtime unless keys exist.

Current CrewAI (docs v1.15): `from crewai import Agent, Task, Crew, Process`
Custom tools subclass `crewai.tools.BaseTool`.
"""

from __future__ import annotations

from typing import Any, Optional

from self_improving_outreach.brand import SYSTEM_CONTEXT
from self_improving_outreach.config import Settings
from self_improving_outreach.crews.pipeline import draft_message
from self_improving_outreach.models import Channel, Draft, Lead, ResearchBundle, ScoreResult
from self_improving_outreach.stores.base import OutreachStore


def crewai_available() -> bool:
    try:
        import crewai  # noqa: F401

        return True
    except Exception:
        return False


def build_you_tool(you_refresh) -> Any:
    from crewai.tools import BaseTool
    from pydantic import BaseModel, Field

    class SearchInput(BaseModel):
        query: str = Field(..., description="Company / CFO research query")

    class YouComSearchTool(BaseTool):
        name: str = "you_com_search"
        description: str = (
            "Search You.com for live company, CFO/CIO, and finance-ops context. "
            "Retries once then degrades to cached ClickHouse context."
        )
        args_schema: type[BaseModel] = SearchInput

        def _run(self, query: str) -> str:
            return you_refresh(query)

    return YouComSearchTool()


def run_crewai_draft(
    settings: Settings,
    lead: Lead,
    research: ResearchBundle,
    score: ScoreResult,
    store: OutreachStore,
    channel: Channel,
) -> Optional[Draft]:
    if not crewai_available():
        return None
    from crewai import Agent, Crew, Process, Task

    patterns = store.list_patterns()
    pattern_blob = "\n".join(f"- {p.pattern_id} ({p.score:.2f}): {p.angle}" for p in patterns[:5])
    researcher = Agent(
        role="Cubiczan Researcher",
        goal="Gather live CFO/CIO and company context for governed finance outreach",
        backstory=SYSTEM_CONTEXT + " You use You.com and never invent filings.",
        verbose=settings.crewai_verbose,
        allow_delegation=False,
    )
    scorer = Agent(
        role="Cubiczan Scorer",
        goal="Explain the deterministic ICP score using stored ClickHouse weights",
        backstory="You do not invent weights. You interpret the numeric score already computed.",
        verbose=settings.crewai_verbose,
        allow_delegation=False,
    )
    drafter = Agent(
        role="Cubiczan Drafter",
        goal="Write a short LinkedIn or email follow-up using winning Cubiczan patterns",
        backstory=SYSTEM_CONTEXT,
        verbose=settings.crewai_verbose,
        allow_delegation=False,
    )
    critic = Agent(
        role="Cubiczan Critic",
        goal="Reject brand misspellings, overclaims, and send-ready language that implies we posted to LinkedIn",
        backstory="Pipeline Scout owns send. You only polish the draft.",
        verbose=settings.crewai_verbose,
        allow_delegation=False,
    )
    research_task = Task(
        description=(
            f"Summarize this live research for {lead.company} / {lead.contact_name} "
            f"({lead.title}). Research:\n{research.as_text()}"
        ),
        expected_output="A 5-bullet CFO/CIO context brief.",
        agent=researcher,
    )
    score_task = Task(
        description=(
            f"ICP score is {score.total}. Features={score.features}. "
            f"Weights={score.weights}. Explain in two sentences why this is or is not Cubiczan ICP."
        ),
        expected_output="Two-sentence ICP rationale.",
        agent=scorer,
        context=[research_task],
    )
    draft_task = Task(
        description=(
            f"Write a {channel.value} note from Sam Desigan at Cubiczan to {lead.contact_name} "
            f"at {lead.company}. Prefer these scored patterns:\n{pattern_blob}\n"
            f"Do not say we already sent it. Brand spelling is Cubiczan."
        ),
        expected_output="A short outreach draft body only.",
        agent=drafter,
        context=[research_task, score_task],
    )
    critic_task = Task(
        description="Critique and return the final draft body only. Fix CubicZan misspelling if present.",
        expected_output="Final draft body.",
        agent=critic,
        context=[draft_task],
    )
    crew = Crew(
        agents=[researcher, scorer, drafter, critic],
        tasks=[research_task, score_task, draft_task, critic_task],
        process=Process.sequential,
        verbose=settings.crewai_verbose,
    )
    result = crew.kickoff()
    body = str(getattr(result, "raw", result)).strip()
    fallback = draft_message(lead, store, channel)
    if not body:
        return fallback
    fallback.body = body
    return fallback
