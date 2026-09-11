import json
from subprocess import CompletedProcess

from self_improving_outreach.config import Settings
from self_improving_outreach.runtime import build_you_client
from self_improving_outreach.tools.one_cli import OneCli
from self_improving_outreach.tools.one_you import OneYouComClient
from self_improving_outreach.tools.you_com import HttpYouComClient, MockYouComClient, YouComError


def _ok(cmd, payload):
    return CompletedProcess(cmd, 0, stdout=json.dumps(payload), stderr="")


def test_one_you_search_and_research_parse_envelopes():
    def runner(cmd, **kwargs):
        action = cmd[5]
        if "TiwS" in action or action.endswith("search"):
            return _ok(
                cmd,
                {
                    "response": {
                        "results": {
                            "web": [
                                {
                                    "title": "Cubiczan close",
                                    "url": "https://cubiczan.com",
                                    "snippets": ["SOX remediation"],
                                }
                            ]
                        }
                    }
                },
            )
        return _ok(
            cmd,
            {"data": {"answer": "Treasury observability matters.", "sources": [{"title": "src", "url": "https://x"}]}},
        )

    client = OneYouComClient("live::you::default::test", runner=OneCli(runner=runner))
    search = client.search("Northline CFO", count=3)
    assert search.source == "one.you.search"
    assert search.snippets[0].title == "Cubiczan close"
    assert "SOX" in search.as_text()
    research = client.research("CFO material weakness")
    assert research.source == "one.you.research"
    assert "Treasury" in research.synthesis


def test_one_you_search_failure_is_youcom_error():
    def runner(cmd, **kwargs):
        return CompletedProcess(cmd, 1, stdout="", stderr="rate limited")

    client = OneYouComClient("live::you::default::test", runner=OneCli(runner=runner))
    try:
        client.search("q")
        raise AssertionError("expected failure")
    except YouComError as exc:
        assert "rate limited" in str(exc)


def test_build_you_client_prefers_one_then_direct_then_mock():
    one_settings = Settings(
        mock_mode=False,
        one_secret="sk-test",
        one_cli_auth=False,
        one_you_connection_key="live::you::default::test",
        you_api_key="ydc-direct",
    )
    client = build_you_client(one_settings)
    assert isinstance(client, OneYouComClient)

    you_only = Settings(
        mock_mode=False,
        one_cli_auth=False,
        you_api_key="ydc-direct",
        research_provider="auto",
    )
    assert isinstance(build_you_client(you_only), HttpYouComClient)

    forced_you = Settings(
        mock_mode=False,
        research_provider="you",
        one_secret="sk-test",
        one_you_connection_key="live::you::default::test",
        you_api_key="ydc-direct",
    )
    assert isinstance(build_you_client(forced_you), HttpYouComClient)

    mock_even_with_one = Settings(
        mock_mode=True,
        one_secret="sk-test",
        one_you_connection_key="live::you::default::test",
    )
    assert isinstance(build_you_client(mock_even_with_one), MockYouComClient)
