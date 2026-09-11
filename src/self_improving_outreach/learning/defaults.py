"""Default Cubiczan ICP weights and message patterns."""

from __future__ import annotations

from self_improving_outreach.brand import DEFAULT_ANGLES
from self_improving_outreach.models import Channel, MessagePattern

DEFAULT_WEIGHTS: dict[str, float] = {
    "cfo_cio_title": 1.20,
    "finance_ops_pain": 1.00,
    "material_weakness_or_sox": 1.40,
    "multi_entity_or_treasury": 0.90,
    "enterprise_or_midmarket": 0.80,
    "agentic_readiness": 0.60,
    "industry_fit": 0.70,
}

TEMPLATES: dict[str, str] = {
    "90-day material-weakness remediation": (
        "Hi {contact_name} — {founder} here from {brand}. Teams with a material-weakness "
        "or SOX finding often spend quarters in slideware. We run a governed multi-agent "
        "90-day remediation: close evidence, recon breaks, and control narratives with "
        "human gates. Worth a 20-minute look at how {company} would stage week 1?"
    ),
    "governed multi-agent close": (
        "Hi {contact_name} — {brand} builds an agentic CFO/CIO layer for the close. "
        "Agents prepare, humans approve. If {company}'s close still hinges on heroics "
        "in recon and flux, I would like to show the governed workflow {founder} uses "
        "with finance teams."
    ),
    "reconciliation automation": (
        "Hi {contact_name} — recon exceptions at {company} are a pattern {brand} agents "
        "are built to classify and route, not a spreadsheet sport. {founder} would value "
        "20 minutes on where your breaks cluster."
    ),
    "treasury observability": (
        "Hi {contact_name} — treasury at {company} should not be a black box between "
        "close cycles. {brand} adds governed agents for cash, facilities, and covenant "
        "observability. Open to a short walkthrough from {founder}?"
    ),
    "agentic CFO/CIO copilot": (
        "Hi {contact_name} — {brand} is the agentic CFO/CIO for governed finance "
        "(close, recon, treasury, observability). Not another chatbot — a crew with "
        "audit trails. {founder} is selecting a few {industry} teams for a working session."
    ),
}

PATTERN_IDS = {
    "90-day material-weakness remediation": "mw-90d",
    "governed multi-agent close": "close-governed",
    "reconciliation automation": "recon-auto",
    "treasury observability": "treasury-obs",
    "agentic CFO/CIO copilot": "cfo-cio-copilot",
}


def default_weights() -> dict[str, float]:
    return dict(DEFAULT_WEIGHTS)


def default_patterns() -> list[MessagePattern]:
    patterns = []
    for angle in DEFAULT_ANGLES:
        patterns.append(
            MessagePattern(
                pattern_id=PATTERN_IDS[angle],
                angle=angle,
                channel=Channel.LINKEDIN,
                template=TEMPLATES[angle],
                score=0.5,
            )
        )
    return patterns
