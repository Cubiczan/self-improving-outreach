"""Update ICP weights and message-pattern scores from outreach outcomes."""

from __future__ import annotations

import logging

from self_improving_outreach.learning.defaults import default_weights
from self_improving_outreach.learning.scorer import extract_features
from self_improving_outreach.models import (
    NEGATIVE_OUTCOMES,
    POSITIVE_OUTCOMES,
    LearnEvent,
    Lead,
    Outcome,
    utcnow,
)
from self_improving_outreach.stores.base import OutreachStore

logger = logging.getLogger(__name__)

LEARNING_RATE = 0.12
WEIGHT_MIN = 0.15
WEIGHT_MAX = 2.5
BAYES_PRIOR = 1.0


def apply_learn_event(
    store: OutreachStore,
    event: LearnEvent,
    lead: Lead | None = None,
    *,
    analytics=None,
) -> dict[str, float]:
    """Mutate store weights + patterns. Returns the updated weight map.

    When the LearnEvent is a LinkedIn accept (Scout / accept-check / live
    outcome), also fires Mixpanel ``linkedin_connect_accepted``. Does not send.
    """
    lead = lead or store.get_lead(event.lead_id)
    features = event.features or (extract_features(lead) if lead else {})
    weights = store.get_weights() or default_weights()
    reward = _reward(event.outcome)
    if reward != 0.0 and features:
        updated = dict(weights)
        for feature, value in features.items():
            current = float(updated.get(feature, default_weights().get(feature, 1.0)))
            current = current + LEARNING_RATE * reward * float(value)
            updated[feature] = min(WEIGHT_MAX, max(WEIGHT_MIN, current))
        store.set_weights(updated)
        weights = updated

    pattern_id = event.pattern_id
    if not pattern_id:
        latest = store.latest_event(event.lead_id)
        pattern_id = latest.pattern_id if latest else None
    if pattern_id:
        _update_pattern(store, pattern_id, event.outcome)
    try:
        from self_improving_outreach.analytics.mixpanel import (
            maybe_track_linkedin_connect_accepted,
        )

        maybe_track_linkedin_connect_accepted(event, lead, analytics=analytics)
    except Exception:
        logger.exception("Mixpanel linkedin_connect_accepted hook failed")
    return weights


def _reward(outcome: Outcome) -> float:
    if outcome in POSITIVE_OUTCOMES:
        return 1.0 if outcome != Outcome.MEETING else 1.4
    if outcome in NEGATIVE_OUTCOMES:
        return -0.8 if outcome != Outcome.THUMBS_DOWN else -1.0
    if outcome == Outcome.SENT:
        return 0.15
    return 0.0


def _update_pattern(store: OutreachStore, pattern_id: str, outcome: Outcome) -> None:
    patterns = {p.pattern_id: p for p in store.list_patterns()}
    pattern = patterns.get(pattern_id)
    if pattern is None:
        return
    pattern.impressions += 1
    if outcome in POSITIVE_OUTCOMES:
        pattern.wins += 1
    elif outcome in NEGATIVE_OUTCOMES:
        pattern.losses += 1
    pattern.score = (pattern.wins + BAYES_PRIOR) / (
        pattern.impressions + 2 * BAYES_PRIOR
    )
    pattern.updated_at = utcnow()
    store.upsert_pattern(pattern)


def simulate_outcome(score_total: float, angle: str) -> Outcome:
    """Deterministic mock outcomes so the swarm can demonstrate learning without CRM."""
    # Material-weakness and treasury angles win more often in mock data — Cubiczan ICP.
    boost = 0.0
    if "material-weakness" in angle:
        boost = 18.0
    elif "treasury" in angle:
        boost = 10.0
    elif "reconcil" in angle:
        boost = 4.0
    adjusted = score_total + boost
    if adjusted >= 72:
        return Outcome.MEETING
    if adjusted >= 58:
        return Outcome.REPLIED
    if adjusted >= 45:
        return Outcome.SENT
    return Outcome.IGNORE
