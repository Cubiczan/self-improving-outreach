"""Cubiczan brand constants used by drafter, critic, and prompts."""

from __future__ import annotations

import re

BRAND = "Cubiczan"
# Case-sensitive tokens. Do not lowercase-compare CubicZan to Cubiczan — they
# differ only by Z and are identical case-insensitively (false-positive source).
BRAND_MISSPELLINGS = ("CubicZan", "cubicZan", "Cubic Zan", "cubic zan")
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

# Spaced form cannot match Cubiczan (no whitespace). Case-insensitive is safe.
_SPACED_BRAND = re.compile(r"cubic\s+zan", re.IGNORECASE)

SYSTEM_CONTEXT = f"""You represent {BRAND} (never misspell as CubicZan).
Founder: {FOUNDER} (also {FOUNDER_ALSO_KNOWN_AS}).
Positioning: {POSITIONING}.
This crew drafts outreach and learns from outcomes. It does not send LinkedIn
or email — Marketing Hunter / Pipeline Scout own send.
"""


def has_brand_misspelling(text: str) -> bool:
    """True when CubicZan or Cubic Zan appears. Cubiczan is never a misspelling."""
    if "CubicZan" in text or "cubicZan" in text:
        return True
    return _SPACED_BRAND.search(text) is not None


def rewrite_brand_spelling(text: str) -> str:
    """Replace forbidden spellings with Cubiczan; leave Cubiczan untouched."""
    rewritten = _SPACED_BRAND.sub(BRAND, text)
    return rewritten.replace("CubicZan", BRAND).replace("cubicZan", BRAND)
