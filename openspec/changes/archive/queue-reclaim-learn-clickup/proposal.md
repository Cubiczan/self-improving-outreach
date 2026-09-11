# Proposal: Queue reclaim, opt-in learn-on-draft, ClickUp ingest

## Why

Sam’s focus is self-improving **search + outreach** only (no paid ads). Operators need to put leads back on the swarm queue, show the Learner moving on a demo/live opt-in path, keep the existing LiveKit transcript hook explicit, and let Pipeline Scout / Marketing Hunter drop a ClickUp “Queued” task into the same queue.

## What

- CLI `requeue` / `queue reset` to set leads back to `queued` by `lead_id`, company, or `--all-sample`, and optionally clear stuck `processing`
- Opt-in `LEARN_ON_DRAFT=true` so a successful draft/`approved_for_scout` can call `simulate_outcome` → `apply_learn_event` even when not in mock mode; default production still learns from real Scout outcomes via `learn`
- Keep `LIVEKIT_FEEDBACK_AUTO` (default false) wired after draft; do not require LiveKit for the text path
- CLI `ingest-clickup` (and `queue upsert --from-json`) to ingest ClickUp task / webhook-shaped JSON as `queued`

## Scope

In: queue reclaim, learn-on-draft setting + pipeline hook, ClickUp mapper CLI, tests, README / `.env.example`, OpenSpec.

Out: Google Ads / Facebook Ads / Meta Ads, paid spend, a full ClickUp webhook HTTP server, Boundless/ClickHouse/One/Daytona behavior changes, LinkedIn send (Pipeline Scout).
