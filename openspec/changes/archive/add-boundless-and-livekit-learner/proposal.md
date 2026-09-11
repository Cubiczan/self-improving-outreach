# Proposal: Boundless LLM provider + LiveKit learner hardening

## Why

Sam has Boundless inference credit (~$50 on boundless.network). Live CrewAI today only looks at `OPENAI_API_KEY`, so those credits cannot power `swarm --once`. Voice learning is a thumbs CLI only — Marketing Hunter / AE preference interviews need a transcript file path into the same Learner, with `outreach_events.metadata.source=livekit`.

## What

- OpenAI-compatible Boundless provider (`LLM_PROVIDER=boundless`) for CrewAI / LiteLLM
- Settings + `show-config` (no secrets) + `.env.example` / README
- LiveKit transcript parse (`voice --transcript-file`) and optional post-draft auto hook (`LIVEKIT_FEEDBACK_AUTO`)
- Persist voice learn events with `source=livekit`; mock mode stays key-free

## Scope

In: Settings, crew adapter, pipeline hook, voice CLI/parse, tests, OpenSpec, README.

Out: Spending real Boundless credits in CI, LiveKit room hosting, LinkedIn send (Pipeline Scout).
