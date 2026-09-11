import json
from subprocess import CompletedProcess

from self_improving_outreach.config import Settings
from self_improving_outreach.observability.tracing import DaytonaTracer, LoggingTracer, build_tracer
from self_improving_outreach.tools.one_cli import OneCli
from self_improving_outreach.tools.one_daytona import OneDaytonaClient


def _ok(cmd, payload):
    return CompletedProcess(cmd, 0, stdout=json.dumps(payload), stderr="")


def test_create_start_list_delete_via_one():
    calls = []

    def runner(cmd, **kwargs):
        calls.append(cmd)
        if cmd[2:4] == ["actions", "search"]:
            query = cmd[5]
            action = {
                "start": "act-start",
                "list": "act-list",
                "delete": "act-delete",
            }
            key = "start" if "start" in query else "list" if "list" in query else "delete"
            return _ok(cmd, {"actions": [{"actionId": action[key]}]})
        if cmd[5] == "conn_mod_def::GMgWX_S6VPA::VxlhHfBWQ4qfa9mXEX2OQQ":
            return _ok(cmd, {"response": {"id": "sbx-99", "state": "started"}})
        return _ok(cmd, {"ok": True})

    client = OneDaytonaClient(
        "live::daytona::default::test",
        runner=OneCli(runner=runner),
    )
    sandbox = client.create({"name": "cubiczan-outreach"})
    assert sandbox.id == "sbx-99"
    listed = client.list()
    assert listed == {"ok": True}
    sandbox.delete()
    execute_cmds = [c for c in calls if c[2:4] == ["actions", "execute"]]
    assert execute_cmds[0][4] == "daytona"
    assert "--path-vars" in execute_cmds[-1]
    assert json.loads(execute_cmds[-1][execute_cmds[-1].index("--path-vars") + 1]) == {
        "sandboxIdOrName": "sbx-99"
    }


def test_tracer_creates_and_deletes_one_sandbox():
    calls = []

    def runner(cmd, **kwargs):
        calls.append(cmd)
        if cmd[2:4] == ["actions", "search"]:
            return _ok(cmd, {"actions": [{"actionId": "act-delete"}]})
        if "execute" in cmd:
            if "-d" in cmd:
                return _ok(cmd, {"id": "sbx-one", "state": "started"})
            return _ok(cmd, {"ok": True})
        return _ok(cmd, {"ok": True})

    settings = Settings(
        mock_mode=True,
        one_secret="sk-test",
        one_cli_auth=False,
        one_daytona_connection_key="live::daytona::default::test",
        daytona_sandbox_runs=True,
        sandbox_provider="auto",
    )
    one_client = OneDaytonaClient(
        settings.one_daytona_connection_key,
        runner=OneCli(runner=runner),
        delete_action_id="act-delete",
    )
    tracer = DaytonaTracer(settings, run_id="run-abcd-1", one_client=one_client)
    assert tracer.sandbox is not None
    assert tracer.sandbox.id == "sbx-one"
    assert any(r["name"] == "daytona.sandbox_created" for r in tracer.records())
    tracer.close()
    assert tracer.sandbox is None
    assert any(c[2:4] == ["actions", "execute"] and c[5] == "act-delete" for c in calls)


def test_build_tracer_one_vs_none():
    one_settings = Settings(
        one_secret="sk-test",
        one_daytona_connection_key="live::daytona::default::test",
        daytona_sandbox_runs=False,
        one_cli_auth=False,
    )
    tracer = build_tracer(one_settings)
    assert isinstance(tracer, DaytonaTracer)
    assert one_settings.effective_sandbox_provider == "one"

    none_settings = Settings(one_cli_auth=False)
    assert none_settings.effective_sandbox_provider == "none"
    assert isinstance(build_tracer(none_settings), LoggingTracer)


def test_sandbox_provider_daytona_skips_one():
    settings = Settings(
        sandbox_provider="daytona",
        one_secret="sk-test",
        one_daytona_connection_key="live::daytona::default::test",
        daytona_api_key="dtn-key",
        one_cli_auth=False,
    )
    assert settings.effective_sandbox_provider == "daytona"
