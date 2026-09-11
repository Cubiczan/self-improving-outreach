import json
from subprocess import CompletedProcess

from self_improving_outreach.config import Settings
from self_improving_outreach.observability.tracing import DaytonaTracer, LoggingTracer, build_tracer
from self_improving_outreach.one_defaults import DEFAULT_DAYTONA_DOCKERFILE, DEFAULT_DAYTONA_SNAPSHOT
from self_improving_outreach.tools.one_cli import OneCli
from self_improving_outreach.tools.one_daytona import (
    OneDaytonaClient,
    merge_sandbox_create_body,
    one_daytona_from_settings,
)


def _ok(cmd, payload):
    return CompletedProcess(cmd, 0, stdout=json.dumps(payload), stderr="")


def _execute_data(cmd):
    return json.loads(cmd[cmd.index("-d") + 1])


def test_merge_sandbox_create_body_fills_buildinfo_and_snapshot():
    body = merge_sandbox_create_body({"name": "cubiczan-outreach", "labels": {"app": "swarm"}})
    assert body["name"] == "cubiczan-outreach"
    assert body["labels"] == {"app": "swarm"}
    assert body["buildInfo"]["dockerfileContent"] == DEFAULT_DAYTONA_DOCKERFILE
    assert body["snapshot"] == DEFAULT_DAYTONA_SNAPSHOT


def test_merge_sandbox_create_body_caller_wins_and_blank_snapshot_omits():
    body = merge_sandbox_create_body(
        {
            "name": "custom",
            "snapshot": "my-snapshot",
            "buildInfo": {"dockerfileContent": "FROM ubuntu:22.04", "contextHashes": ["h1"]},
        }
    )
    assert body["snapshot"] == "my-snapshot"
    assert body["buildInfo"]["dockerfileContent"] == "FROM ubuntu:22.04"
    assert body["buildInfo"]["contextHashes"] == ["h1"]

    omitted = merge_sandbox_create_body({"name": "n"}, snapshot="")
    assert "snapshot" not in omitted
    assert omitted["buildInfo"]["dockerfileContent"] == DEFAULT_DAYTONA_DOCKERFILE

    env_override = merge_sandbox_create_body(
        {"name": "n"},
        dockerfile="FROM ubuntu:22.04",
        snapshot="daytonaio/sandbox:latest",
    )
    assert env_override["buildInfo"]["dockerfileContent"] == "FROM ubuntu:22.04"
    assert env_override["snapshot"] == "daytonaio/sandbox:latest"


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
    create_cmd = execute_cmds[0]
    assert "-d" in create_cmd
    assert "--skip-validation" not in create_cmd
    created = _execute_data(create_cmd)
    assert created["name"] == "cubiczan-outreach"
    assert created["buildInfo"]["dockerfileContent"] == DEFAULT_DAYTONA_DOCKERFILE
    assert created["snapshot"] == DEFAULT_DAYTONA_SNAPSHOT
    assert "--path-vars" in execute_cmds[-1]
    assert json.loads(execute_cmds[-1][execute_cmds[-1].index("--path-vars") + 1]) == {
        "sandboxIdOrName": "sbx-99"
    }


def test_create_uses_client_dockerfile_and_snapshot_overrides():
    calls = []

    def runner(cmd, **kwargs):
        calls.append(cmd)
        return _ok(cmd, {"id": "sbx-1", "state": "started"})

    client = OneDaytonaClient(
        "live::daytona::default::test",
        runner=OneCli(runner=runner),
        dockerfile="FROM ubuntu:22.04",
        snapshot="",
    )
    client.create({"name": "named-only"})
    created = _execute_data(next(c for c in calls if "-d" in c))
    assert created["name"] == "named-only"
    assert created["buildInfo"]["dockerfileContent"] == "FROM ubuntu:22.04"
    assert "snapshot" not in created
    assert "--skip-validation" not in calls[0]


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
    create_cmd = next(c for c in calls if c[2:4] == ["actions", "execute"] and "-d" in c)
    created = _execute_data(create_cmd)
    assert created["name"] == "cubiczan-outreach-run-abcd"
    assert created["buildInfo"]["dockerfileContent"] == DEFAULT_DAYTONA_DOCKERFILE
    assert created["snapshot"] == DEFAULT_DAYTONA_SNAPSHOT
    assert "--skip-validation" not in create_cmd
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


def test_from_settings_wires_create_defaults():
    calls = []

    def runner(cmd, **kwargs):
        calls.append(cmd)
        return _ok(cmd, {"id": "sbx-settings", "state": "started"})

    settings = Settings(
        one_daytona_connection_key="live::daytona::default::test",
        one_daytona_dockerfile="FROM ubuntu:22.04",
        one_daytona_snapshot="",
        one_cli_auth=False,
    )
    client = one_daytona_from_settings(settings, runner=OneCli(runner=runner))
    sandbox = client.create()
    assert sandbox.id == "sbx-settings"
    created = _execute_data(next(c for c in calls if "-d" in c))
    assert created["buildInfo"]["dockerfileContent"] == "FROM ubuntu:22.04"
    assert "snapshot" not in created
    assert "--skip-validation" not in calls[0]


def test_sandbox_provider_daytona_skips_one():
    settings = Settings(
        sandbox_provider="daytona",
        one_secret="sk-test",
        one_daytona_connection_key="live::daytona::default::test",
        daytona_api_key="dtn-key",
        one_cli_auth=False,
    )
    assert settings.effective_sandbox_provider == "daytona"
