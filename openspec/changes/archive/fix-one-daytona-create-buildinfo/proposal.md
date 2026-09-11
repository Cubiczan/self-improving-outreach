# Proposal: One Daytona create must send buildInfo

## Why

`DaytonaTracer` calls `OneDaytonaClient.create({"name": name})` when `DAYTONA_SANDBOX_RUNS=true`. A non-empty body disables `--skip-validation`, and One’s create-sandbox action schema requires `buildInfo` (and `buildInfo.dockerfileContent`). Empty create is not the live path, so Cubiczan swarm tracing sandboxes fail with `Validation failed missing required parameter buildInfo`.

## What

- Merge a default create body in `one_daytona.create` so name/labels-only callers still send `buildInfo.dockerfileContent` (minimal Dockerfile) and an optional Daytona `snapshot`.
- Env overrides: `ONE_DAYTONA_DOCKERFILE`, `ONE_DAYTONA_SNAPSHOT`.
- Do not treat `--skip-validation` as the only fix.
- Unit tests stay mocked (no live One in CI).

## Scope

In: One Daytona create payload, Settings / `.env.example` / README, OpenSpec one-integrations, unit tests.

Out: Live One/Daytona calls in CI, You.com adapters, LinkedIn send.
