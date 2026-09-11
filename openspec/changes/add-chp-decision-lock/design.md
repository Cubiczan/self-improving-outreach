# Design

## Protocol mapping

Cubiczan CHP (`consensus-hardening-protocol` / `cme.chp`) is the decision-governance layer. This repo implements the five P0 holes for outreach without a hard package dependency.

| CHP concept | Outreach implementation |
| --- | --- |
| R0 gate (solvable / scoped / valid / worth_it) | `evaluate_r0_gate` — local copy; soft-import `cme.chp.gates.evaluate_r0_gate` when present |
| Foundation commit before peers contaminate | Independently sealed research, score, and draft digests, then a composed R0 envelope |
| Adversarial foundation attack | Deterministic structural adversary; cannot be skipped when the flag is on |
| Third-party validation | Named human `approve` / `deny` (empty / `system` / `auto` / `anonymous` rejected) |
| Payload integrity | SHA-256 canonical JSON; evidence pack digest = R0 + adversary + lock |
| `LOCKED` only for downstream | `approved_for_scout` requires `locked` + verified pack |

State machine (lead / session phase):

```text
exploring → advisory → provisional → locked → approved_for_scout
```

- **exploring** — R0 sealed; adversary has not finished
- **advisory** — structural adversary recorded against the sealed R0
- **provisional** — awaiting named human lock (pipeline stops here)
- **locked** — named approve + immutable evidence pack
- **approved_for_scout** — pack verified; Pipeline Scout may send out of band

Deny stays `provisional` (or `pending_review`). The pipeline never sends.

## Flag

`CHP_LOCK_ENABLED` is optional. Unset → **true when not mock**, **false when mock** so CI and `uv run pytest` stay on the existing critic → gate path. Explicit `true`/`false` always wins. Live (`MOCK_MODE=false` with keys) therefore defaults to lock-required.

When the flag is off, `apply_human_gate` is unchanged (`HUMAN_GATE_ENABLED` → `pending_review`, else `approved_for_scout`).

## R0 before peers see each other

Research, score, and draft each seal a digest over **only that peer’s fields**. Composition of the R0 envelope happens after all three seals exist. The adversary and the human receive the sealed envelope; they cannot rewrite peer payloads. Recomputing any seal must match or the session is rejected.

R0 gate HALT (empty company/body, unscoped draft, brand-invalid body, worthless empty score payload) records the commit but refuses later lock.

## Adversary

Structural, deterministic, always invoked when the flag is on. No `skip_adversary` path. Checks: Cubiczan misspelling, missing brand, overclaims, send-implication language, empty/too-long body, degraded research without disclosure.

PR 9’s CrewAI Adversary Critic (when that branch lands) may attach `adversary_notes` on the draft. Those notes are copied into the pack as `crewai_adversary_notes`. They **do not** replace or skip the structural pass. Score and Learner stay in Python.

## Named lock and evidence pack

`chp lock --lead-id … --approve|--deny --actor "Sam Desigan"`. Actor is required and must be a named human. Approve requires sealed R0 (PASS), a present adversary report, then seals an immutable pack. Mutating pack fields after seal raises. Promote to `approved_for_scout` only after `verify_evidence_pack`.

Decisions persist on the store and on `CHP_DECISIONS_PATH` (`chp_decisions.jsonl`) so a later CLI process can lock a MemoryStore run.

## Persistence

`MemoryStore` holds decisions in-process. ClickHouse gets `chp_decisions` (`002_chp_lock.sql`). Migrate applies every `migrations/clickhouse/*.sql` when pointed at the directory.

## Reconciliation with PR 9

PR 9 (`cursor/expand-crewai-utilization-0065`) adds `CREWAI_MODE`, You.com tools, Strategist, and a prompt-level Adversary Critic. This change does **not** land that adapter. It fills the P0 holes PR 9 left as “soft CHP inspiration”: sealed R0, non-skippable structural adversary, named lock, immutable pack, lock-gated `approved_for_scout`. The two compose: PR 9 may enrich prose; this lock governs send-readiness.
