# Proposal: Fix Daytona One import cycle and SDK region

## Why

Live traces with `SANDBOX_PROVIDER=auto|one` fail during `DaytonaTracer` init: importing One Daytona pulls `tools/__init__.py` → You.com → `stores.base` → `chp` package init → `chp.session` → `OutreachStore` while `stores.base` is still loading. Direct SDK create then fails when the org has no dashboard default region. Local `LoggingTracer` spans must keep working if OTEL has no collector.

## What

- Break the circular import with lazy / `TYPE_CHECKING` imports (no large refactor).
- Pass `DaytonaConfig.target` from `DAYTONA_TARGET` or `DAYTONA_REGION` so SDK create does not require only the dashboard default.
- Keep `agent_runs.traces` spans; `daytona.client_ready` / `daytona.sandbox_created` / `daytona.init_failed` stay accurate. OTEL export to an unreachable localhost collector degrades (no process hang).
- Unit tests mock One CLI and the Daytona SDK. Document One vs SDK and the region requirement.

## Scope

In: One Daytona import graph, DaytonaTracer SDK create, Settings / README / `.env.example`, OpenSpec one-integrations, unit tests.

Out: Live One/Daytona keys in CI, CHP / CrewAI / You.com behavior changes, invented metrics.
