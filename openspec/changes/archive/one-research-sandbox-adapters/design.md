# Design

## Transport

The repo has no One HTTP client today. The documented agent surface is the One CLI:

```
one --agent actions search <platform> "query" -t execute
one --agent actions knowledge <platform> <actionId>
one --agent actions execute <platform> <actionId> <connectionKey> -d '{...}'
```

A small `OneCli` subprocess wrapper is the adapter. It inherits the process environment so `ONE_SECRET` works, and it also works when the operator already ran `one init` / `one login` (CLI config, no secret in `.env`). Tests replace `subprocess.run`. We do not call live One in CI.

Action definition IDs are not secrets. Documented defaults (overridable via env):

| Platform | Action | Default action id |
| --- | --- | --- |
| you | Search Unified Web and News (`POST /v1/search`) | `conn_mod_def::GK9ryNdQKGE::TiwS_VVUSE-wxbKljY4T4g` |
| you | Research (`POST /v1/research`) | `conn_mod_def::GK9rx6bXINM::MUbK6JMcTwWoiaxT6DmEIQ` |
| daytona | Create a Sandbox (`POST /api/sandbox`) | `conn_mod_def::GMgWX_S6VPA::VxlhHfBWQ4qfa9mXEX2OQQ` |

Start / list / delete sandbox action IDs are optional env knobs. When sandbox runs are enabled and an id is missing, the runner MAY `actions search` then `knowledge` before execute.

Connection keys are env-only. Example shape (do not commit live values): `live::you::default::<id>`.

## Provider selection

`RESEARCH_PROVIDER` and `SANDBOX_PROVIDER` default to `auto`.

- **auto**: One when auth + that platform’s connection key are present; else the direct client; else mock / no sandbox.
- **one**: prefer One; fall back to direct then mock if One is not configured (so local/CI still works).
- **you** / **daytona**: skip One; use the existing HTTP/SDK path (or mock / none).

Auth is `ONE_SECRET`, explicit `ONE_CLI_AUTH=true`, or a local One config (`.onerc` / `~/.one/config.json`). `ONE_CLI_AUTH=false` disables filesystem/CLI probing (tests set this).

`MOCK_MODE=true` still forces `MockYouComClient` and does not create sandboxes. `is_mock` auto-mode treats One You as a live research credential (same as `YDC_API_KEY`).

## Runtime wiring

`build_you_client` returns `OneYouComClient` when the effective research provider is `one`. That client implements `YouSearcher` (`search` / `contents` / `research`) and reuses the existing bundle parsers. `ResilientYouCom` is unchanged (retry once, then cache).

`DaytonaTracer` creates/deletes a sandbox through `OneDaytonaClient` when the effective sandbox provider is `one` and `DAYTONA_SANDBOX_RUNS=true`. Direct SDK init remains when the effective provider is `daytona`. Tracing spans still land on `agent_runs` without any Daytona path.

`show-config` reports `research_provider` and `sandbox_provider` as the **effective** path (`one` / `you` / `mock` and `one` / `daytona` / `none`), plus booleans `one_configured`, `one_you_configured`, `one_daytona_configured`. Never print secrets or connection keys.

## Failover

One execute/search failures raise `YouComError` / `OneError` so the existing retry-then-cache path and worker isolation still apply. Missing One config is not an error in `auto` — it falls through.
