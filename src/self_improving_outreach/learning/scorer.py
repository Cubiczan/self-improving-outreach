"""Deterministic ICP scorer. Weights live in ClickHouse / memory and are learner-updated."""

from __future__ import annotations

from self_improving_outreach.learning.defaults import default_weights
from self_improving_outreach.models import Lead, ResearchBundle, ScoreResult
from self_improving_outreach.stores.base import OutreachStore

FINANCE_TITLES = (
    "cfo",
    "cio",
    "controller",
    "vp finance",
    "vp of finance",
    "chief financial",
    "chief information",
    "head of finance",
    "treasurer",
)
PAIN_KEYWORDS = (
    "close",
    "reconcil",
    "sox",
    "material weakness",
    "audit",
    "treasury",
    "covenant",
    "flux",
    "erp",
)
MW_KEYWORDS = ("material weakness", "sox", "404", "icfr", "significant deficiency")
TREASURY_KEYWORDS = ("treasury", "multi-entity", "multi entity", "cash", "covenant")
INDUSTRY_FIT = (
    "bank",
    "manufactur",
    "insurance",
    "healthcare",
    "saas",
    "software",
    "industrial",
    "energy",
    "private equity",
    "pe-backed",
)


def extract_features(lead: Lead, research: ResearchBundle | None = None) -> dict[str, float]:
    blob = " ".join(
        [
            lead.title,
            lead.industry,
            lead.company,
            " ".join(str(v) for v in lead.signals.values()),
            research.as_text() if research else "",
            lead.cached_context,
        ]
    ).lower()
    title = lead.title.lower()
    return {
        "cfo_cio_title": 1.0 if any(token in title for token in FINANCE_TITLES) else 0.0,
        "finance_ops_pain": 1.0 if any(token in blob for token in PAIN_KEYWORDS) else 0.0,
        "material_weakness_or_sox": 1.0 if any(token in blob for token in MW_KEYWORDS) else 0.0,
        "multi_entity_or_treasury": 1.0 if any(token in blob for token in TREASURY_KEYWORDS) else 0.0,
        "enterprise_or_midmarket": _size_feature(lead),
        "agentic_readiness": 1.0
        if any(token in blob for token in ("agent", "automation", "ai ", "copilot"))
        else 0.3,
        "industry_fit": 1.0 if any(token in blob for token in INDUSTRY_FIT) else 0.2,
    }


def _size_feature(lead: Lead) -> float:
    employees = lead.signals.get("employees")
    if isinstance(employees, (int, float)):
        if employees >= 200:
            return 1.0
        if employees >= 50:
            return 0.7
        return 0.3
    return 0.6


def score_lead(
    lead: Lead,
    store: OutreachStore,
    research: ResearchBundle | None = None,
) -> ScoreResult:
    weights = store.get_weights() or default_weights()
    features = extract_features(lead, research)
    total = 0.0
    parts = []
    for feature, value in features.items():
        weight = float(weights.get(feature, 0.0))
        contrib = weight * value
        total += contrib
        parts.append(f"{feature}={value:.2f}×{weight:.2f}")
    # Bound to 0-100 style display without hiding relative ranking.
    display = round(min(100.0, max(0.0, total * 20.0)), 2)
    return ScoreResult(
        total=display,
        features=features,
        weights={k: float(weights.get(k, 0.0)) for k in features},
        rationale="; ".join(parts),
    )
