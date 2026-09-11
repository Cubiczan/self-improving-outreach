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
