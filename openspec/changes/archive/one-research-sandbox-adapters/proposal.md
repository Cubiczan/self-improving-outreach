# Proposal: One adapters for You.com research and Daytona sandboxes

## Why

Sam connected You.com and Daytona on One (withone.ai). Swarm research and optional sandbox runs still talk only to `YDC_API_KEY` / `DAYTONA_API_KEY` HTTP/SDK clients. When One is already authenticated, those paths should prefer One connections and keep the direct-key clients as fallback for mock/local.

## What

- Invoke One via `one --agent` CLI (honors `ONE_SECRET` or existing CLI auth). Connection keys come from env (`ONE_YOU_CONNECTION_KEY`, `ONE_DAYTONA_CONNECTION_KEY`) — never hardcoded live keys.
- `RESEARCH_PROVIDER=one|you|auto` and `SANDBOX_PROVIDER=one|daytona|auto` (default `auto`).
- You.com Search / Research through One `you` actions when configured; Daytona create/start/list/delete through One `daytona` actions when sandbox runs are on.
- Direct You.com HTTP and Daytona SDK remain the fallback. Mock mode stays key-free.
- Honest `show-config` (booleans + effective provider, no secrets). Unit tests mock subprocess so CI does not need live One.

## Scope

In: Settings, One CLI runner, You.com + Daytona adapters, tracer/runtime wiring, tests, `.env.example`, README, OpenSpec.

Out: Gmail via One, LinkedIn send, Boundless/LiveKit/ClickHouse behavior changes, live One calls in CI.
