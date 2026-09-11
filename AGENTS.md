# Agent notes

This repository uses OpenSpec. Read `openspec/AGENTS.md` and `openspec/specs/` before changing outreach, scoring, swarm, or integrations.

Brand spelling is **Cubiczan**. Pipeline Scout / Marketing Hunter own LinkedIn send.

Live CrewAI can use Boundless (`LLM_PROVIDER=boundless`) as an OpenAI-compatible provider. Never commit API keys. Voice transcripts feed the Learner with `metadata.source=livekit`.

You.com research and Daytona sandboxes prefer One when `ONE_SECRET` (or CLI auth) plus `ONE_YOU_CONNECTION_KEY` / `ONE_DAYTONA_CONNECTION_KEY` are set; otherwise the direct `YDC_API_KEY` / `DAYTONA_API_KEY` clients remain.
