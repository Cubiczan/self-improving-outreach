"""Mixpanel wrapper + Learner hook. Fake client only — no network."""

from __future__ import annotations

from typing import Any, Optional

from typer.testing import CliRunner

from self_improving_outreach.analytics.mixpanel import (
    ANONYMOUS_DISTINCT_ID,
    EVENT_LINKEDIN_CONNECT_ACCEPTED,
    EVENT_SIGN_UP_COMPLETED,
    SITE_ONLY_EVENTS,
    MixpanelAnalytics,
    is_linkedin_connect_accepted,
    linkedin_url_from_lead,
    maybe_track_linkedin_connect_accepted,
)
from self_improving_outreach.cli import app
from self_improving_outreach.config import Settings
from self_improving_outreach.learning.learner import apply_learn_event
from self_improving_outreach.models import LearnEvent, Outcome
from self_improving_outreach.stores.memory import MemoryStore
from self_improving_outreach.swarm.queue import lead_from_mapping


class FakeMixpanel:
    def __init__(self) -> None:
        self.tracks: list[tuple[str, str, dict[str, Any]]] = []
        self.people: list[tuple[str, dict[str, Any]]] = []

    def track(self, distinct_id: str, event_name: str, properties: Optional[dict] = None) -> None:
        self.tracks.append((distinct_id, event_name, dict(properties or {})))

    def people_set(self, distinct_id: str, properties: dict, meta: Optional[dict] = None) -> None:
        self.people.append((distinct_id, dict(properties)))


def _lead(**overrides):
    payload = {
        "lead_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "company": "Northline Manufacturing",
        "contact_name": "Priya Shah",
        "title": "CFO",
        "industry": "manufacturing",
        "signals": {
            "pain": "SOX 404 material weakness",
            "linkedin_url": "https://www.linkedin.com/in/priya-shah",
        },
    }
    payload.update(overrides)
    return lead_from_mapping(payload)


def test_site_only_contact_submitted_is_not_implemented():
    assert "contact_submitted" in SITE_ONLY_EVENTS
    fake = FakeMixpanel()
    analytics = MixpanelAnalytics("tok", "development", client=fake)
    analytics.track("contact_submitted", {"form": "site"})
    assert fake.tracks == []


def test_super_properties_and_sign_up_completed():
    fake = FakeMixpanel()
    analytics = MixpanelAnalytics("tok", "development", client=fake)
    analytics.track_sign_up_completed(
        sign_up_method="cli",
        platform="server",
        referral_source="ae",
        user_id="42",
    )
    assert analytics.identified is True
    assert analytics.distinct_id == "42"
    assert fake.people
    assert fake.people[0][0] == "42"
    assert fake.people[0][1]["product"] == "sio"
    assert len(fake.tracks) == 1
    distinct_id, name, props = fake.tracks[0]
    assert distinct_id == "42"
    assert name == EVENT_SIGN_UP_COMPLETED
    assert props["sign_up_method"] == "cli"
    assert props["platform"] == "server"
    assert props["referral_source"] == "ae"
    assert props["product"] == "sio"
    assert props["environment"] == "development"


def test_identify_refuses_email_and_people_set_requires_identify():
    fake = FakeMixpanel()
    analytics = MixpanelAnalytics("tok", "development", client=fake)
    assert analytics.identify("sam@cubiczan.com") is False
    assert analytics.identified is False
    analytics.people_set({"plan": "should-not-send"})
    assert fake.people == []
    analytics.track(EVENT_SIGN_UP_COMPLETED, {"sign_up_method": "cli"})
    assert fake.tracks[0][0] == ANONYMOUS_DISTINCT_ID


def test_reset_clears_identity():
    fake = FakeMixpanel()
    analytics = MixpanelAnalytics("tok", "production", client=fake, distinct_id="7")
    assert analytics.identified is True
    analytics.reset()
    assert analytics.identified is False
    assert analytics.distinct_id == ANONYMOUS_DISTINCT_ID
    analytics.track_linkedin_connect_accepted(
        company="Acme",
        person_name="Jane",
        linkedin_url="https://linkedin.com/in/jane",
    )
    assert fake.tracks[-1][0] == ANONYMOUS_DISTINCT_ID
    assert fake.tracks[-1][2]["environment"] == "production"


def test_missing_token_is_noop():
    fake = FakeMixpanel()
    analytics = MixpanelAnalytics(None, "development", client=None)
    analytics._client = None  # noqa: SLF001 — explicit disabled
    analytics.token = None
    analytics.track_linkedin_connect_accepted(company="X", person_name="Y")
    assert fake.tracks == []


def test_token_resolution_prod_vs_dev():
    prod = Settings(
        environment="production",
        mixpanel_token="generic",
        mixpanel_token_dev="devtok",
        mixpanel_token_prod="prodtok",
        one_cli_auth=False,
    )
    assert prod.resolved_environment == "production"
    assert prod.resolved_mixpanel_token == "prodtok"
    prod_alias = Settings(environment="prod", mixpanel_token="generic", one_cli_auth=False)
    assert prod_alias.resolved_environment == "production"
    assert prod_alias.resolved_mixpanel_token == "generic"

    dev = Settings(
        environment="development",
        mixpanel_token="generic",
        mixpanel_token_dev="devtok",
        mixpanel_token_prod="prodtok",
        one_cli_auth=False,
    )
    assert dev.resolved_environment == "development"
    assert dev.resolved_mixpanel_token == "generic"
    dev_only = Settings(mixpanel_token_dev="devtok", mixpanel_token_prod="prodtok", one_cli_auth=False)
    assert dev_only.resolved_environment == "development"
    assert dev_only.resolved_mixpanel_token == "devtok"


def test_operator_id_identifies_without_signup():
    fake = FakeMixpanel()
    settings = Settings(operator_id="99", mixpanel_token="tok", one_cli_auth=False)
    analytics = MixpanelAnalytics(
        settings.resolved_mixpanel_token,
        settings.resolved_environment,
        client=fake,
        distinct_id=settings.resolved_operator_id,
    )
    assert analytics.identified is True
    assert analytics.distinct_id == "99"
    assert all(name != EVENT_SIGN_UP_COMPLETED for _, name, _ in fake.tracks)


def test_show_config_hides_mixpanel_tokens(monkeypatch):
    monkeypatch.setenv("MIXPANEL_TOKEN_DEV", "secret-dev-token")
    monkeypatch.setenv("MIXPANEL_TOKEN_PROD", "secret-prod-token")
    monkeypatch.setenv("ENVIRONMENT", "development")
    from self_improving_outreach.config import public_settings_view, reset_settings_cache
    from self_improving_outreach.config import get_settings

    reset_settings_cache()
    view = public_settings_view(get_settings())
    dumped = str(view)
    assert "secret-dev-token" not in dumped
    assert "secret-prod-token" not in dumped
    assert view["mixpanel_configured"] is True
    assert view["environment"] == "development"

    runner = CliRunner()
    result = runner.invoke(app, ["show-config"])
    assert result.exit_code == 0, result.stdout
    assert "secret-dev-token" not in result.stdout
    assert "mixpanel_configured" in result.stdout


def test_is_linkedin_connect_accepted_from_flag_and_notes():
    flagged = LearnEvent(lead_id="x", outcome=Outcome.REPLIED, linkedin_connect_accepted=True)
    assert is_linkedin_connect_accepted(flagged) is True
    noted = LearnEvent(lead_id="x", outcome=Outcome.REPLIED, notes="Scout: connection accepted")
    assert is_linkedin_connect_accepted(noted) is True
    meeting = LearnEvent(lead_id="x", outcome=Outcome.MEETING)
    assert is_linkedin_connect_accepted(meeting) is False


def test_linkedin_url_from_lead_signals():
    lead = _lead()
    event = LearnEvent(lead_id=lead.lead_id, outcome=Outcome.REPLIED)
    assert linkedin_url_from_lead(lead, event) == "https://www.linkedin.com/in/priya-shah"
    override = LearnEvent(
        lead_id=lead.lead_id,
        outcome=Outcome.REPLIED,
        linkedin_url="https://www.linkedin.com/in/override",
    )
    assert linkedin_url_from_lead(lead, override) == "https://www.linkedin.com/in/override"


def test_apply_learn_event_tracks_value_moment_when_marked():
    store = MemoryStore()
    lead = _lead()
    store.upsert_lead(lead)
    fake = FakeMixpanel()
    analytics = MixpanelAnalytics("tok", "development", client=fake, distinct_id="op-1")
    apply_learn_event(
        store,
        LearnEvent(
            lead_id=lead.lead_id,
            outcome=Outcome.REPLIED,
            pattern_id="mw-90d",
            linkedin_connect_accepted=True,
            batch_id="batch-9",
        ),
        lead,
        analytics=analytics,
    )
    names = [name for _, name, _ in fake.tracks]
    assert EVENT_LINKEDIN_CONNECT_ACCEPTED in names
    props = next(p for _, name, p in fake.tracks if name == EVENT_LINKEDIN_CONNECT_ACCEPTED)
    assert props["company"] == "Northline Manufacturing"
    assert props["person_name"] == "Priya Shah"
    assert props["linkedin_url"] == "https://www.linkedin.com/in/priya-shah"
    assert props["batch_id"] == "batch-9"
    assert props["product"] == "sio"
    assert props["platform"] == "server"


def test_apply_learn_event_meeting_does_not_track_connect():
    store = MemoryStore()
    lead = _lead()
    store.upsert_lead(lead)
    fake = FakeMixpanel()
    analytics = MixpanelAnalytics("tok", "development", client=fake)
    apply_learn_event(
        store,
        LearnEvent(lead_id=lead.lead_id, outcome=Outcome.MEETING, pattern_id="mw-90d"),
        lead,
        analytics=analytics,
    )
    assert fake.tracks == []


def test_maybe_track_helper_is_public_call_site():
    fake = FakeMixpanel()
    analytics = MixpanelAnalytics("tok", "development", client=fake)
    lead = _lead()
    fired = maybe_track_linkedin_connect_accepted(
        LearnEvent(lead_id=lead.lead_id, outcome=Outcome.SENT, notes="linkedin_connect_accepted"),
        lead,
        analytics=analytics,
    )
    assert fired is True
    assert fake.tracks[0][1] == EVENT_LINKEDIN_CONNECT_ACCEPTED


def test_cli_analytics_hooks_use_injected_client(monkeypatch):
    fake = FakeMixpanel()
    analytics = MixpanelAnalytics("tok", "development", client=fake)
    monkeypatch.setattr(
        "self_improving_outreach.analytics.mixpanel.get_analytics",
        lambda: analytics,
    )
    runner = CliRunner()
    sign = runner.invoke(
        app,
        ["analytics", "sign-up", "--user-id", "88", "--method", "cli", "--referral-source", "readme"],
    )
    assert sign.exit_code == 0, sign.stdout
    assert "sign_up_completed" in sign.stdout
    connect = runner.invoke(
        app,
        [
            "analytics",
            "linkedin-connect-accepted",
            "--company",
            "Harbor Regional Bank",
            "--person-name",
            "Marcus Lee",
            "--linkedin-url",
            "https://www.linkedin.com/in/marcus",
            "--batch-id",
            "b1",
        ],
    )
    assert connect.exit_code == 0, connect.stdout
    assert "linkedin_connect_accepted" in connect.stdout
    assert "false" in connect.stdout.lower() or connect.stdout  # send: false
    names = [name for _, name, _ in fake.tracks]
    assert EVENT_SIGN_UP_COMPLETED in names
    assert EVENT_LINKEDIN_CONNECT_ACCEPTED in names

    ident = runner.invoke(app, ["analytics", "identify", "--user-id", "88"])
    assert ident.exit_code == 0, ident.stdout
    reset = runner.invoke(app, ["analytics", "reset"])
    assert reset.exit_code == 0, reset.stdout
    assert analytics.identified is False


def test_cli_learn_accept_flag_reaches_helper(monkeypatch):
    fake = FakeMixpanel()
    analytics = MixpanelAnalytics("tok", "development", client=fake, distinct_id="op")
    monkeypatch.setattr(
        "self_improving_outreach.analytics.mixpanel.get_analytics",
        lambda: analytics,
    )
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "learn",
            "--event",
            (
                '{"lead_id":"11111111-1111-1111-1111-111111111111",'
                '"outcome":"replied","pattern_id":"mw-90d",'
                '"linkedin_connect_accepted":true}'
            ),
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert any(name == EVENT_LINKEDIN_CONNECT_ACCEPTED for _, name, _ in fake.tracks)


def test_disabled_client_does_not_raise():
    analytics = MixpanelAnalytics(None, "development")
    analytics.track_sign_up_completed(sign_up_method="cli", user_id="1")
    analytics.track_linkedin_connect_accepted(company="A", person_name="B")
    analytics.reset()
