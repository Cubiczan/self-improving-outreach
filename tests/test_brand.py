from self_improving_outreach.brand import (
    BRAND,
    has_brand_misspelling,
    rewrite_brand_spelling,
)
from self_improving_outreach.crews.pipeline import critique_draft, draft_message
from self_improving_outreach.models import Channel, Draft
from self_improving_outreach.stores.memory import MemoryStore
from self_improving_outreach.swarm.queue import lead_from_mapping


def _draft(body: str) -> Draft:
    return Draft(
        pattern_id="mw-90d",
        angle="90-day material-weakness remediation",
        body=body,
        channel=Channel.LINKEDIN,
    )


def test_has_brand_misspelling_rejects_cubicZan_not_cubiczan():
    assert not has_brand_misspelling("Hi from Cubiczan — governed close.")
    assert has_brand_misspelling("Hi from CubicZan — governed close.")
    assert has_brand_misspelling("Hi from Cubic Zan — governed close.")
    assert has_brand_misspelling("Hi from cubic zan — governed close.")
    assert rewrite_brand_spelling("CubicZan and Cubic Zan") == f"{BRAND} and {BRAND}"
    assert rewrite_brand_spelling("Cubiczan") == "Cubiczan"


def test_critic_accepts_correct_cubiczan_spelling():
    critique = critique_draft(_draft("Hi Priya — Sam Desigan here from Cubiczan."))
    assert "brand misspelling" not in critique.issues
    assert critique.revised_body is not None
    assert "Cubiczan" in critique.revised_body
    assert "CubicZan" not in critique.revised_body


def test_critic_rejects_cubicZan_and_rewrites():
    critique = critique_draft(_draft("Hi there from CubicZan — we aim to help."))
    assert "brand misspelling" in critique.issues
    assert critique.accepted is False
    assert "CubicZan" not in (critique.revised_body or "")
    assert "Cubiczan" in (critique.revised_body or "")


def test_critic_rejects_cubic_zan_spacing():
    critique = critique_draft(_draft("Hello from Cubic Zan on close automation."))
    assert "brand misspelling" in critique.issues
    assert "Cubic Zan" not in (critique.revised_body or "")
    assert "Cubiczan" in (critique.revised_body or "")


def test_deterministic_draft_is_not_flagged_for_brand():
    store = MemoryStore()
    lead = lead_from_mapping(
        {
            "company": "Northline Manufacturing",
            "contact_name": "Priya Shah",
            "title": "CFO",
            "industry": "manufacturing",
        }
    )
    draft = draft_message(lead, store, Channel.LINKEDIN)
    critique = critique_draft(draft)
    assert "Cubiczan" in draft.body
    assert "brand misspelling" not in critique.issues
