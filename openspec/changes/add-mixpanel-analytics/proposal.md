# Proposal: Mixpanel analytics (Phase 6)

## Why

Full Implementation Phase 6 needs production Mixpanel wiring for Cubiczan self-improving-outreach so value moments and identity can land in the Cubiczan Development / ImpactQuadrant LLC projects without inventing a signup or LinkedIn send path.

## What

- Official Mixpanel Python SDK (`mixpanel` 4.x) behind an env-token wrapper
- Super properties `product=sio`, `platform=server`, `environment=production|development`
- Events: `sign_up_completed` (helper + CLI; no fake signup), `linkedin_connect_accepted` (value moment on Learner / Scout accept outcomes)
- `contact_submitted` is site-only and is **not** implemented here
- `identify(user_id)` on a stable operator pk (never email); `reset()` helper (no logout exists); `people.set` only when identified
- No consent gate. Analytics failures MUST NOT break the pipeline. No LinkedIn send.

## Scope

In: Settings / `.env.example` / README / `AGENTS.md`, analytics module, Learner + CLI hooks, mocked tests, OpenSpec.

Out: Site `contact_submitted`, LinkedIn send, inventing an account-creation or logout flow, network calls in CI.
