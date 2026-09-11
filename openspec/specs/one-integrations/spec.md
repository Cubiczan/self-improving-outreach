# One Integrations Specification

## Purpose

Run Cubiczan swarm research and optional Daytona sandbox lifecycle through One (withone.ai) connections when they are configured, without requiring live One in CI.

## Requirements

### Requirement: Prefer One when configured

The system SHALL invoke One via the `one --agent` CLI when `ONE_SECRET` or One CLI auth is available **and** the platform connection key is set. Connection keys SHALL come from environment variables (`ONE_YOU_CONNECTION_KEY`, `ONE_DAYTONA_CONNECTION_KEY`) and SHALL NOT be hardcoded in source. Direct You.com HTTP (`YOU_API_KEY` / `YDC_API_KEY`) and Daytona SDK (`DAYTONA_API_KEY`) SHALL remain available as fallbacks.

#### Scenario: Auto prefers One You research

- GIVEN `RESEARCH_PROVIDER=auto`, One auth, `ONE_YOU_CONNECTION_KEY`, and `MOCK_MODE=false`
- WHEN Researcher refreshes a lead
- THEN the YouSearcher SHALL execute the One `you` Search (or Research) action
- AND `show-config` SHALL report `research_provider` as `one`
- AND no connection key or `ONE_SECRET` value SHALL appear in `show-config`

#### Scenario: Auto falls back to direct You.com

- GIVEN `RESEARCH_PROVIDER=auto`, no One You connection key, and `YDC_API_KEY` set
- WHEN Researcher refreshes a lead
- THEN the existing You.com HTTP client SHALL be used
- AND `show-config` SHALL report `research_provider` as `you`

#### Scenario: Mock mode ignores One

- GIVEN `MOCK_MODE=true` and One connection keys present
- WHEN a lead is researched
- THEN `MockYouComClient` SHALL run and no One CLI process is required

### Requirement: Provider knobs

The system SHALL read `RESEARCH_PROVIDER=one|you|auto` (default `auto`) and `SANDBOX_PROVIDER=one|daytona|auto` (default `auto`). Invalid values SHALL be rejected. `one` prefers One and SHALL fall back to the direct client (then mock / none) when One is not configured so local and CI still work. `you` / `daytona` SHALL skip One.

#### Scenario: Explicit you skips One

- GIVEN `RESEARCH_PROVIDER=you`, One You ready, and `YDC_API_KEY` set
- WHEN the research client is built
- THEN the direct HTTP You.com client SHALL be used

### Requirement: Daytona sandbox via One

When `SANDBOX_PROVIDER` resolves to `one`, `DAYTONA_SANDBOX_RUNS=true`, and `ONE_DAYTONA_CONNECTION_KEY` is set, the tracer SHALL create (and on close, delete) a sandbox by executing One `daytona` actions. Start / list / delete MAY resolve action IDs via `actions search` when not configured. When One Daytona is not configured, the existing Daytona SDK path SHALL be used if `DAYTONA_API_KEY` is present.

#### Scenario: Sandbox create through One

- GIVEN `SANDBOX_PROVIDER=auto`, One Daytona ready, and `DAYTONA_SANDBOX_RUNS=true`
- WHEN a `DaytonaTracer` session starts
- THEN it SHALL execute the One Daytona create-sandbox action
- AND `show-config` SHALL report `sandbox_provider` as `one`

#### Scenario: No sandbox without keys

- GIVEN no Daytona API key and no One Daytona connection key
- WHEN a run is traced
- THEN spans SHALL still record locally
- AND no sandbox SHALL be created

### Requirement: One Daytona create payload includes buildInfo

When creating a sandbox through One, `OneDaytonaClient.create` SHALL merge defaults so the execute `-d` body includes `buildInfo.dockerfileContent` even when the caller only passes `name` and/or `labels`. The body MAY also include `snapshot`. Defaults SHALL be overridable via `ONE_DAYTONA_DOCKERFILE` and `ONE_DAYTONA_SNAPSHOT`. Caller-supplied `buildInfo` and `snapshot` SHALL win. Execute SHALL NOT rely on `--skip-validation` as the only way to satisfy One’s create-sandbox schema. Tests SHALL mock the CLI (no live One).

#### Scenario: Name-only create satisfies One schema

- GIVEN One Daytona ready
- WHEN `create({"name": "cubiczan-outreach"})` runs
- THEN the execute `-d` body SHALL contain `buildInfo.dockerfileContent`
- AND the body MAY contain `snapshot`
- AND the execute command SHALL NOT pass `--skip-validation`

#### Scenario: Caller buildInfo and snapshot win

- GIVEN a create call with explicit `buildInfo.dockerfileContent` and `snapshot`
- WHEN defaults are merged
- THEN the execute body SHALL keep the caller Dockerfile and snapshot

### Requirement: One Daytona imports without store cycle

Importing `self_improving_outreach.tools.one_daytona` (including `one_daytona_from_settings`) SHALL succeed without raising a circular-import error for `OutreachStore` on `self_improving_outreach.stores.base`. `DaytonaTracer` SHALL be able to construct an One Daytona client when One is configured. Tests SHALL cover this import path without live One.

#### Scenario: Isolated one_daytona import

- GIVEN a fresh interpreter
- WHEN `from self_improving_outreach.tools.one_daytona import one_daytona_from_settings` runs
- THEN the import SHALL succeed
- AND `OutreachStore` SHALL remain importable from `stores.base`

#### Scenario: Tracer One init does not fail on import

- GIVEN `SANDBOX_PROVIDER=auto`, One Daytona ready, and `DAYTONA_SANDBOX_RUNS=false`
- WHEN a `DaytonaTracer` session starts
- THEN it SHALL emit `daytona.client_ready` with `provider=one`
- AND it SHALL NOT emit `daytona.init_failed` due to an `OutreachStore` circular import

### Requirement: Direct SDK sandbox region

When the effective sandbox provider is `daytona`, SDK sandbox create SHALL send an explicit runner target when `DAYTONA_TARGET` or `DAYTONA_REGION` is set (`DaytonaConfig.target`). An organization default region in the Daytona Dashboard remains sufficient when env is unset. README SHALL state that org default **or** explicit env is required.

#### Scenario: Env target is passed to DaytonaConfig

- GIVEN `SANDBOX_PROVIDER=daytona`, `DAYTONA_API_KEY`, `DAYTONA_SANDBOX_RUNS=true`, and `DAYTONA_TARGET=us`
- WHEN a `DaytonaTracer` session starts
- THEN the SDK client SHALL be constructed with `target=us`
- AND `daytona.client_ready` / `daytona.sandbox_created` SHALL record `provider=daytona`

### Requirement: Local spans survive missing OTEL collector

`LoggingTracer` spans SHALL always record on `agent_runs.traces`. When Daytona OTEL is requested but the OTLP endpoint is the default loopback collector and that collector is not reachable, the tracer SHALL disable SDK OTEL export instead of hanging or treating the run as `daytona.init_failed`.

#### Scenario: No collector on localhost:4318

- GIVEN `DAYTONA_OTEL_ENABLED=true` and no process listening on the default OTLP HTTP port
- WHEN a `DaytonaTracer` SDK session starts
- THEN local spans SHALL still record
- AND the process SHALL NOT block on OTLP export
- AND sandbox init SHALL NOT fail solely because the collector is down
