from self_improving_outreach.learning.learner import apply_learn_event
from self_improving_outreach.learning.scorer import extract_features, score_lead
from self_improving_outreach.models import LearnEvent, Outcome
from self_improving_outreach.stores.memory import MemoryStore
from self_improving_outreach.swarm.queue import lead_from_mapping


def _cfo_lead():
    return lead_from_mapping(
        {
            "lead_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "company": "Northline Manufacturing",
            "contact_name": "Priya Shah",
            "title": "CFO",
            "industry": "manufacturing",
            "signals": {"pain": "SOX 404 material weakness", "employees": 1200},
        }
    )


def test_cfo_material_weakness_scores_higher_than_generic():
    store = MemoryStore()
    strong = score_lead(_cfo_lead(), store)
    weak = score_lead(
        lead_from_mapping(
            {
                "company": "Local Bakery",
                "title": "Owner",
                "industry": "food",
                "signals": {"employees": 8},
            }
        ),
        store,
    )
    assert strong.total > weak.total
    assert strong.features["cfo_cio_title"] == 1.0
    assert strong.features["material_weakness_or_sox"] == 1.0


def test_meeting_outcome_increases_matching_weights():
    store = MemoryStore()
    lead = _cfo_lead()
    store.upsert_lead(lead)
    before = store.get_weights()["cfo_cio_title"]
    features = extract_features(lead)
    apply_learn_event(
        store,
        LearnEvent(
            lead_id=lead.lead_id,
            outcome=Outcome.MEETING,
            pattern_id="mw-90d",
            features=features,
        ),
        lead,
    )
    after = store.get_weights()["cfo_cio_title"]
    assert after > before
    pattern = next(p for p in store.list_patterns() if p.pattern_id == "mw-90d")
    assert pattern.wins == 1
    assert pattern.score > 0.5


def test_ignore_outcome_decreases_weights_and_pattern_score():
    store = MemoryStore()
    lead = _cfo_lead()
    store.upsert_lead(lead)
    before = store.get_weights()["industry_fit"]
    apply_learn_event(
        store,
        LearnEvent(
            lead_id=lead.lead_id,
            outcome=Outcome.IGNORE,
            pattern_id="cfo-cio-copilot",
            features=extract_features(lead),
        ),
        lead,
    )
    assert store.get_weights()["industry_fit"] < before
    pattern = next(p for p in store.list_patterns() if p.pattern_id == "cfo-cio-copilot")
    assert pattern.losses == 1
    assert pattern.score < 0.5
