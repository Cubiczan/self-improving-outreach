# Agent notes

This repository uses OpenSpec. Read `openspec/AGENTS.md` and `openspec/specs/` before changing outreach, scoring, swarm, or integrations.

Brand spelling is **Cubiczan**. Pipeline Scout / Marketing Hunter own LinkedIn send.

When `CHP_LOCK_ENABLED` resolves true (default on live), drafts stay `provisional` until a named human lock seals an immutable evidence pack. No auto-send. Score and Learner stay deterministic.

Live CrewAI can use Boundless (`LLM_PROVIDER=boundless`) as an OpenAI-compatible provider. `CREWAI_MODE=off|draft|full` (default `full` when `use_crewai`) is draft-brain only and MUST NOT bypass the CHP lock. Never commit API keys. Voice transcripts feed the Learner with `metadata.source=livekit`.

You.com research and Daytona sandboxes prefer One when `ONE_SECRET` (or CLI auth) plus `ONE_YOU_CONNECTION_KEY` / `ONE_DAYTONA_CONNECTION_KEY` are set; otherwise the direct `YDC_API_KEY` / `DAYTONA_API_KEY` clients remain.
