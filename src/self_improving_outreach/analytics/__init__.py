"""Mixpanel product analytics for Cubiczan self-improving-outreach.

``contact_submitted`` is site-only and is not implemented in this Python package.
"""

from self_improving_outreach.analytics.mixpanel import (
    EVENT_LINKEDIN_CONNECT_ACCEPTED,
    EVENT_SIGN_UP_COMPLETED,
    SITE_ONLY_EVENTS,
    MixpanelAnalytics,
    get_analytics,
    identify,
    is_linkedin_connect_accepted,
    linkedin_url_from_lead,
    maybe_track_linkedin_connect_accepted,
    reset,
    reset_analytics_cache,
    track_linkedin_connect_accepted,
    track_sign_up_completed,
)

__all__ = [
    "EVENT_LINKEDIN_CONNECT_ACCEPTED",
    "EVENT_SIGN_UP_COMPLETED",
    "SITE_ONLY_EVENTS",
    "MixpanelAnalytics",
    "get_analytics",
    "identify",
    "is_linkedin_connect_accepted",
    "linkedin_url_from_lead",
    "maybe_track_linkedin_connect_accepted",
    "reset",
    "reset_analytics_cache",
    "track_linkedin_connect_accepted",
    "track_sign_up_completed",
]
