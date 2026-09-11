"""Cubiczan brand constants used by drafter, critic, and prompts."""

from __future__ import annotations

BRAND = "Cubiczan"
BRAND_MISSPELLINGS = ("CubicZan", "cubic zan", "Cubic Zan")
FOUNDER = "Sam Desigan"
FOUNDER_ALSO_KNOWN_AS = "Shyam Desigan"
POSITIONING = (
    "agentic CFO/CIO — governed multi-agent finance for close, reconciliation, "
    "treasury, and observability, including 90-day material-weakness remediation"
)
PILLARS = (
    "close",
    "reconciliation",
    "treasury",
    "observability",
    "material-weakness remediation",
)
DEFAULT_ANGLES = (
    "90-day material-weakness remediation",
    "governed multi-agent close",
    "reconciliation automation",
    "treasury observability",
    "agentic CFO/CIO copilot",
)

SYSTEM_CONTEXT = f"""You represent {BRAND} (never misspell as CubicZan).
Founder: {FOUNDER} (also {FOUNDER_ALSO_KNOWN_AS}).
Positioning: {POSITIONING}.
This crew drafts outreach and learns from outcomes. It does not send LinkedIn
or email — Marketing Hunter / Pipeline Scout own send.
"""
