# Proposal: Cubiczan self-improving outreach scaffold

## Why

Cubiczan sales outreach needs a production-ready agent loop that remembers what messaging and ICP angles worked, adapts when tools fail, refreshes with live web data, and can optionally interview via voice — without sending LinkedIn itself.

## What

- CrewAI (or mock) crews: Researcher, Scorer, Drafter, Critic, Learner
- ClickHouse schema + in-memory fallback
- You.com search/research/contents with one retry then cache degrade
- Daytona tracing interface wrapping each run
- Optional LiveKit preference-interview module
- Swarm orchestrator with concurrency, `--once`, and `--loop`
- CLI, tests, docker-compose, env templates

## Scope

In: text crew, swarm, learning, mock mode, docs, migrations.

Out: actual LinkedIn send (Marketing Hunter / Pipeline Scout), production ClickHouse provisioning, paid API calls in CI.
