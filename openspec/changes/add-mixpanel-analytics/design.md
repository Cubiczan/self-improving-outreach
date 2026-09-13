# Design: Mixpanel analytics

## Tokens

Read from env only. Never hardcode project tokens in Python as the only path.

| Environment | Token resolution |
| --- | --- |
| `ENVIRONMENT` in `prod`, `production` | `MIXPANEL_TOKEN_PROD` or `MIXPANEL_TOKEN` |
| otherwise (default development) | `MIXPANEL_TOKEN` or `MIXPANEL_TOKEN_DEV` |

Documented example values live in `.env.example` (Cubiczan Development / ImpactQuadrant LLC). Missing token → no-op client. `show-config` reports `mixpanel_configured` and `environment` only — never the token.

## Official SDK

Use `mixpanel>=4.10.1,<5` (`from mixpanel import Mixpanel`). The 5.x line pulls a tighter Pydantic pin that we do not want. Wrapper merges super properties on every `track`. Tests inject a fake client; no network.

Python SDK has no JS-style `identify` / `reset`. The wrapper holds `distinct_id` in process memory:

- `identify(user_id)` — refuse values that look like email
- `reset()` — clear identity (CLI hook; this repo has no logout)
- `people_set` — only after identify; minimal attrs (`product`, `platform`, `environment`)

If `OPERATOR_ID` or `MIXPANEL_DISTINCT_ID` is set, the client identifies on first construct. That is **not** `sign_up_completed`.

## Events

| Event | Where |
| --- | --- |
| `sign_up_completed` | Public helper + `analytics sign-up` CLI. Properties: `sign_up_method`, `platform`, optional `referral_source`. No account-creation path exists in this repo; do not invent one. |
| `linkedin_connect_accepted` | **Value moment.** Public `track_linkedin_connect_accepted(...)`. Called from `apply_learn_event` when the LearnEvent is marked as a LinkedIn accept (explicit flag, notes, or outcome alias). Properties: `company`, `person_name`, `linkedin_url`, optional `batch_id`. |
| `contact_submitted` | Site-only. Documented; not implemented in this Python product. |

Simulated mock swarm outcomes do **not** fire the value moment unless the LearnEvent is explicitly marked.

## Identity

Stable operator id = DB pk or env `OPERATOR_ID` / `MIXPANEL_DISTINCT_ID`, never email. Unidentified tracks use distinct_id `anonymous`.
