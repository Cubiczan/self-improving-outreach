import json
from subprocess import CompletedProcess

import pytest

from self_improving_outreach.tools.one_cli import (
    OneCli,
    OneError,
    extract_action_id,
    unwrap_one_response,
)


def _ok(cmd, payload):
    return CompletedProcess(cmd, 0, stdout=json.dumps(payload), stderr="")


def test_execute_builds_agent_command():
    seen = {}

    def runner(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["kwargs"] = kwargs
        return _ok(cmd, {"response": {"id": "sbx-1"}})

    client = OneCli(runner=runner, extra_env={"ONE_SECRET": "sk-test"})
    payload = client.execute(
        "you",
        "act-search",
        "live::you::default::test",
        data={"query": "CFO close", "count": 5},
    )
    assert payload["response"]["id"] == "sbx-1"
    assert seen["cmd"][:4] == ["one", "--agent", "actions", "execute"]
    assert seen["cmd"][4:7] == ["you", "act-search", "live::you::default::test"]
    assert "-d" in seen["cmd"]
    assert json.loads(seen["cmd"][seen["cmd"].index("-d") + 1]) == {"query": "CFO close", "count": 5}
    assert seen["kwargs"]["env"]["ONE_SECRET"] == "sk-test"


def test_execute_nonzero_raises_without_leaking_key():
    def runner(cmd, **kwargs):
        return CompletedProcess(cmd, 2, stdout="", stderr="unauthorized")

    client = OneCli(runner=runner)
    with pytest.raises(OneError, match="unauthorized"):
        client.execute("you", "act", "live::you::default::secret-key")


def test_search_and_knowledge_and_resolve():
    calls = []

    def runner(cmd, **kwargs):
        calls.append(cmd)
        if "search" in cmd:
            return _ok(cmd, {"actions": [{"actionId": "conn_mod_def::found", "name": "Delete"}]})
        return _ok(cmd, {"ok": True})

    client = OneCli(runner=runner)
    assert client.resolve_action_id("daytona", "delete sandbox") == "conn_mod_def::found"
    assert client.resolve_action_id("daytona", "delete sandbox", "already-set") == "already-set"
    assert any(cmd[2:5] == ["actions", "search", "daytona"] for cmd in calls)


def test_missing_binary_raises():
    def runner(cmd, **kwargs):
        raise FileNotFoundError("one")

    with pytest.raises(OneError, match="not found"):
        OneCli(runner=runner).whoami()


def test_unwrap_and_extract_helpers():
    assert unwrap_one_response({"response": {"data": {"id": "x"}}}) == {"id": "x"}
    assert unwrap_one_response({"results": {"web": []}}) == {"results": {"web": []}}
    assert extract_action_id({"results": [{"action_id": "abc"}]}) == "abc"
    assert extract_action_id([]) is None
