from self_improving_outreach.models import Lead
from self_improving_outreach.observability.tracing import LoggingTracer
from self_improving_outreach.stores.memory import MemoryStore
from self_improving_outreach.tools.you_com import MockYouComClient, ResilientYouCom, YouComError


def test_youcom_retries_once_then_succeeds():
    store = MemoryStore()
    lead = Lead(company="Harbor Regional Bank", title="CIO", cached_context="bank recon")
    store.upsert_lead(lead)
    client = MockYouComClient(fail_times=1)
    tracer = LoggingTracer()
    bundle = ResilientYouCom(client, store, tracer).refresh(lead, run_id="run-1")
    assert bundle.degraded is False
    assert client.calls == 2
    failures = store.list_tool_failures("run-1")
    assert len(failures) == 1
    assert failures[0].degraded is False


def test_youcom_degrades_to_cached_context_after_two_failures():
    store = MemoryStore()
    lead = Lead(
        company="Orbit Ledger SaaS",
        title="VP Finance",
        cached_context="treasury observability across 9 entities",
    )
    store.upsert_lead(lead)
    client = MockYouComClient(fail_times=5)
    tracer = LoggingTracer()
    bundle = ResilientYouCom(client, store, tracer).refresh(lead, "run-2")
    assert bundle.degraded is True
    assert bundle.source == "cache"
    assert "treasury" in bundle.as_text()
    failures = store.list_tool_failures("run-2")
    assert len(failures) == 2
    assert failures[-1].degraded is True
    assert any("tool_failure" in record["name"] for record in tracer.records())


def test_mock_client_can_raise():
    client = MockYouComClient(fail_times=1)
    try:
        client.search("anything")
        raise AssertionError("expected failure")
    except YouComError:
        pass
    bundle = client.search("anything")
    assert bundle.source == "mock"
