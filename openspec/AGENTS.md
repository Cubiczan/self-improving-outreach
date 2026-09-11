# OpenSpec instructions

This repository uses OpenSpec as the living documentation layer.

- Current behavior lives in `openspec/specs/<capability>/spec.md`.
- In-progress work lives in `openspec/changes/<change-id>/`.
- Completed changes are archived under `openspec/changes/archive/`.

When changing outreach, scoring, learning, swarm, CHP lock, or integrations, update the relevant spec (or add a change proposal) before expanding scope.

Boundless is an OpenAI-compatible LLM provider (`openspec/specs/llm-provider/spec.md`). Voice transcripts feed the Learner with `metadata.source=livekit`.

You.com research and Daytona sandboxes prefer One (`openspec/specs/one-integrations/spec.md`) when `ONE_SECRET` or CLI auth plus connection keys are set.
