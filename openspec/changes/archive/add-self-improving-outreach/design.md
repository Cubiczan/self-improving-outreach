# Design

## Runtime modes

`Settings.is_mock` is true when `MOCK_MODE=true` or when LLM/You.com keys are absent. Mock mode is first-class: CI and local demos never require secrets.

## Pipeline vs CrewAI

Deterministic Python owns scoring, pattern selection, brand critique, weight updates, and failover. CrewAI agents (when `crewai` and `OPENAI_API_KEY` are present) generate research synthesis and prose; they call the same You.com tool wrapper. If CrewAI is missing or the LLM call fails, the deterministic crew still completes the unit of work.

## Stores

`OutreachStore` protocol with `MemoryStore` and `ClickHouseStore`. Swarm workers share one store instance; memory operations are lock-protected so concurrent learners cannot corrupt weights.

## You.com

HTTP client against `https://ydc-index.io/v1/search`, `https://ydc-index.io/v1/contents`, and `https://api.you.com/v1/research`. Auth header `X-API-Key` from `YOU_API_KEY` or `YDC_API_KEY`. Optional `youdotcom` SDK if installed. Fail once, retry once, then cached context + `tool_failures` row.

## Daytona

`RunTracer` protocol. `DaytonaTracer` initializes `daytona.Daytona(DaytonaConfig(api_key, api_url, otel_enabled=True))` when the SDK and key exist; otherwise `LoggingTracer` records spans onto `agent_runs`. Sandbox execution is opt-in (`DAYTONA_SANDBOX_RUNS`) because wrapping every draft in a VM is not required for MVP.

## Swarm

`ThreadPoolExecutor` with `concurrency` workers. Each worker wraps `pipeline.run` in try/except. JSON queue for mock; ClickHouse `leads.status='queued'` for live. `--loop` sleeps `--interval` seconds between batches.

## Voice

`self_improving_outreach.voice.livekit_agent` scaffolds LiveKit Agents `AgentServer` / `AgentSession`. Core text crew does not import or start LiveKit.
