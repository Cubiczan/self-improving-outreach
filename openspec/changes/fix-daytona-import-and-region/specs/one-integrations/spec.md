## ADDED Requirements

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
