# Agent notes

This repository uses OpenSpec. Read `openspec/AGENTS.md` and `openspec/specs/` before changing outreach, scoring, swarm, or integrations.

Brand spelling is **Cubiczan**. Pipeline Scout / Marketing Hunter own LinkedIn send.

When `CHP_LOCK_ENABLED` resolves true (default on live), drafts stay `provisional` until a named human lock seals an immutable evidence pack. No auto-send. Score and Learner stay deterministic.

Live CrewAI can use Boundless (`LLM_PROVIDER=boundless`) as an OpenAI-compatible provider. `CREWAI_MODE=off|draft|full` (default `full` when `use_crewai`) is draft-brain only and MUST NOT bypass the CHP lock. Never commit API keys. Voice transcripts feed the Learner with `metadata.source=livekit`.

You.com research and Daytona sandboxes prefer One when `ONE_SECRET` (or CLI auth) plus `ONE_YOU_CONNECTION_KEY` / `ONE_DAYTONA_CONNECTION_KEY` are set; otherwise the direct `YDC_API_KEY` / `DAYTONA_API_KEY` clients remain.

## Mixpanel analytics

Official Python SDK (`mixpanel` 4.x). Tokens from env only — never hardcode as the only path. No consent gate. Failures must not break the pipeline. This package does **not** send LinkedIn.

Token resolution:

- `ENVIRONMENT` in `prod` / `production` → `MIXPANEL_TOKEN_PROD` or `MIXPANEL_TOKEN` (ImpactQuadrant LLC)
- otherwise → `MIXPANEL_TOKEN` or `MIXPANEL_TOKEN_DEV` (Cubiczan Development; default)

Example values are documented in `.env.example`. Missing token → no-op.

Super properties on every event: `product=sio`, `platform=server`, `environment=production|development`.

Events implemented here:

| Event | When |
| --- | --- |
| `sign_up_completed` | Public helper + `analytics sign-up`. Properties: `sign_up_method`, `platform`, optional `referral_source`. This repo has **no signup flow** — call the helper/CLI when a stable operator pk is first established. Do not invent a fake path. |
| `linkedin_connect_accepted` | **Value moment.** `track_linkedin_connect_accepted(...)` from Learner live outcomes (`apply_learn_event` when `linkedin_connect_accepted` is set or notes mark an accept) and `analytics linkedin-connect-accepted`. Properties: `company`, `person_name`, `linkedin_url`, optional `batch_id`. Does not send. |
| `contact_submitted` | **Site-only.** Do not implement in this Python product. |

Identity:

- `identify(user_id)` with a stable operator/user **pk** (`OPERATOR_ID` or `MIXPANEL_DISTINCT_ID`, or CLI `--user-id`). Never email.
- `reset()` on logout — this repo has no logout; use `analytics reset`.
- `people.set` only after identify; minimal attrs (`product`, `platform`, `environment`).
