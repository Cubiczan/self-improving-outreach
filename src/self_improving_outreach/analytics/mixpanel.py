"""Official Mixpanel Python SDK wrapper. Env tokens only; no LinkedIn send.

Server-side Mixpanel has no JS-style identify/reset. This wrapper holds
``distinct_id`` in process memory and merges super properties on every track.
Missing token or SDK → no-op. Failures never raise to the pipeline.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Optional, Protocol

from self_improving_outreach.config import Settings, get_settings
from self_improving_outreach.models import Lead, LearnEvent

logger = logging.getLogger(__name__)

EVENT_SIGN_UP_COMPLETED = "sign_up_completed"
EVENT_LINKEDIN_CONNECT_ACCEPTED = "linkedin_connect_accepted"
# Cubiczan marketing site owns this event. Do not track it from SIO.
SITE_ONLY_EVENTS = frozenset({"contact_submitted"})

SUPER_PRODUCT = "sio"
SUPER_PLATFORM = "server"
ANONYMOUS_DISTINCT_ID = "anonymous"

_ACCEPT_NOTE_MARKERS = (
    "linkedin_connect_accepted",
    "connect_accepted",
    "linkedin accept",
    "connection accepted",
)


class MixpanelClient(Protocol):
    def track(self, distinct_id: str, event_name: str, properties: Optional[dict] = None) -> None: ...

    def people_set(self, distinct_id: str, properties: dict, meta: Optional[dict] = None) -> None: ...


def looks_like_email(value: str) -> bool:
    text = (value or "").strip()
    return "@" in text and "." in text.split("@")[-1]


def linkedin_url_from_lead(lead: Lead | None, event: LearnEvent | None = None) -> str:
    if event is not None and event.linkedin_url:
        return event.linkedin_url.strip()
    if lead is None:
        return ""
    signals = lead.signals or {}
    for key in ("linkedin_url", "linkedin", "linkedin_profile", "profile_url"):
        raw = signals.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return ""


def is_linkedin_connect_accepted(event: LearnEvent) -> bool:
    """True when Scout / accept-check / live learn marks a LinkedIn accept."""
    if event.linkedin_connect_accepted:
        return True
    notes = (event.notes or "").lower()
    if any(marker in notes for marker in _ACCEPT_NOTE_MARKERS):
        return True
    return False


class MixpanelAnalytics:
    """Process-local Mixpanel client. Safe to call when unconfigured."""

    def __init__(
        self,
        token: Optional[str],
        environment: str,
        *,
        client: MixpanelClient | None = None,
        distinct_id: Optional[str] = None,
        identify_on_init: bool = True,
    ) -> None:
        self.token = (token or "").strip() or None
        self.environment = environment if environment == "production" else "development"
        self._client = client
        self._distinct_id: Optional[str] = None
        self._identified = False
        if self._client is None and self.token:
            self._client = _build_official_client(self.token)
        if identify_on_init and distinct_id:
            self.identify(distinct_id)

    @property
    def enabled(self) -> bool:
        return bool(self.token and self._client)

    @property
    def identified(self) -> bool:
        return self._identified

    @property
    def distinct_id(self) -> str:
        return self._distinct_id or ANONYMOUS_DISTINCT_ID

    def super_properties(self) -> dict[str, str]:
        return {
            "product": SUPER_PRODUCT,
            "platform": SUPER_PLATFORM,
            "environment": self.environment,
        }

    def identify(self, user_id: str) -> bool:
        """Bind a stable operator/user pk. Refuses email-shaped ids."""
        uid = str(user_id or "").strip()
        if not uid:
            return False
        if looks_like_email(uid):
            logger.warning("Mixpanel identify refused email-shaped id")
            return False
        self._distinct_id = uid
        self._identified = True
        self.people_set(
            {
                "product": SUPER_PRODUCT,
                "platform": SUPER_PLATFORM,
                "environment": self.environment,
            }
        )
        return True

    def reset(self) -> None:
        """Clear in-process identity. This repo has no logout route; CLI hooks this."""
        self._distinct_id = None
        self._identified = False

    def people_set(self, properties: dict[str, Any]) -> None:
        if not self.enabled or not self._identified or not self._distinct_id:
            return
        try:
            self._client.people_set(self._distinct_id, dict(properties))
        except Exception:
            logger.exception("Mixpanel people_set failed")

    def track(
        self,
        event_name: str,
        properties: Optional[dict[str, Any]] = None,
        *,
        distinct_id: Optional[str] = None,
    ) -> None:
        if event_name in SITE_ONLY_EVENTS:
            logger.info("Skipping site-only Mixpanel event %s", event_name)
            return
        if not self.enabled:
            return
        payload = {**self.super_properties(), **(properties or {})}
        did = (distinct_id or "").strip() or self.distinct_id
        try:
            self._client.track(did, event_name, payload)
        except Exception:
            logger.exception("Mixpanel track failed for %s", event_name)

    def track_sign_up_completed(
        self,
        *,
        sign_up_method: str,
        platform: str = SUPER_PLATFORM,
        referral_source: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        if user_id:
            self.identify(user_id)
        props: dict[str, Any] = {
            "sign_up_method": sign_up_method,
            "platform": platform,
        }
        if referral_source:
            props["referral_source"] = referral_source
        self.track(EVENT_SIGN_UP_COMPLETED, props)

    def track_linkedin_connect_accepted(
        self,
        *,
        company: str,
        person_name: str,
        linkedin_url: str = "",
        batch_id: Optional[str] = None,
    ) -> None:
        props: dict[str, Any] = {
            "company": company,
            "person_name": person_name,
            "linkedin_url": linkedin_url or "",
        }
        if batch_id:
            props["batch_id"] = batch_id
        self.track(EVENT_LINKEDIN_CONNECT_ACCEPTED, props)


def _build_official_client(token: str) -> MixpanelClient | None:
    try:
        from mixpanel import Mixpanel
    except ImportError:
        logger.warning("mixpanel package is not installed; analytics disabled")
        return None
    try:
        return Mixpanel(token)
    except Exception:
        logger.exception("Failed to construct Mixpanel client")
        return None


def build_analytics(
    settings: Optional[Settings] = None,
    *,
    client: MixpanelClient | None = None,
) -> MixpanelAnalytics:
    settings = settings or get_settings()
    return MixpanelAnalytics(
        settings.resolved_mixpanel_token,
        settings.resolved_environment,
        client=client,
        distinct_id=settings.resolved_operator_id,
    )


@lru_cache(maxsize=1)
def get_analytics() -> MixpanelAnalytics:
    return build_analytics()


def reset_analytics_cache() -> None:
    clear = getattr(get_analytics, "cache_clear", None)
    if callable(clear):
        clear()


def identify(user_id: str) -> bool:
    return get_analytics().identify(user_id)


def reset() -> None:
    get_analytics().reset()


def track_sign_up_completed(
    *,
    sign_up_method: str,
    platform: str = SUPER_PLATFORM,
    referral_source: Optional[str] = None,
    user_id: Optional[str] = None,
) -> None:
    """Fire after a real account is created, or from the CLI when identity is first set.

    This repo has no signup flow. Call this helper (or ``analytics sign-up``)
    when a stable operator pk is first established. Do not invent a fake path.
    """
    get_analytics().track_sign_up_completed(
        sign_up_method=sign_up_method,
        platform=platform,
        referral_source=referral_source,
        user_id=user_id,
    )


def track_linkedin_connect_accepted(
    *,
    company: str,
    person_name: str,
    linkedin_url: str = "",
    batch_id: Optional[str] = None,
) -> None:
    """Value moment: a LinkedIn connection was accepted.

    Does not send LinkedIn. Call from accept-check / Scout / Learner live
    outcomes, or use ``analytics linkedin-connect-accepted``.
    """
    get_analytics().track_linkedin_connect_accepted(
        company=company,
        person_name=person_name,
        linkedin_url=linkedin_url,
        batch_id=batch_id,
    )


def maybe_track_linkedin_connect_accepted(
    event: LearnEvent,
    lead: Lead | None = None,
    *,
    analytics: MixpanelAnalytics | None = None,
) -> bool:
    """Call site for Learner / Scout live outcomes. No-op unless marked as accept."""
    if not is_linkedin_connect_accepted(event):
        return False
    tracker = analytics or get_analytics()
    tracker.track_linkedin_connect_accepted(
        company=(lead.company if lead else ""),
        person_name=(lead.contact_name if lead else ""),
        linkedin_url=linkedin_url_from_lead(lead, event),
        batch_id=event.batch_id or event.run_id,
    )
    return True
