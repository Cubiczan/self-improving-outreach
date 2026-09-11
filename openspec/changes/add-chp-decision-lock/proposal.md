# Proposal: CHP decision lock before approved_for_scout

## Why

Self Improving Outreach can mark a draft `approved_for_scout` after a code critic (and an optional human-gate stub) with no sealed foundation, no independent adversary, and no named human lock. Open PR 9 adds a CrewAI Adversary Critic as prompt inspiration only — it is skippable when CrewAI is off, does not seal R0 before peers see each other, and does not produce an immutable evidence pack. Pipeline Scout must not receive a send-ready lead until Consensus Hardening Protocol (CHP) has locked the decision.

## What

- Feature flag `CHP_LOCK_ENABLED` (default **true on live**, false in mock / unset CI)
- Sealed **R0 foundation commit** from independently sealed research / score / draft peers before those peers’ payloads are composed
- **Non-skippable structural adversary** (deterministic; CrewAI notes from PR 9 are additive only)
- **Named human lock** (`approve` / `deny`) that is the only path into `locked`
- **Immutable evidence pack** hashing R0 + adversary + lock
- `approved_for_scout` requires `locked` + a verified pack when the flag is on
- State machine: `exploring` → `advisory` → `provisional` → `locked` → `approved_for_scout`
- No auto-send. Score math and Learner updates stay deterministic Python

## Scope

In: OpenSpec, CHP session module, pipeline gate wiring, store + ClickHouse table, CLI lock/show, tests, README mermaid, settings / `.env.example`.

Out: LinkedIn/email send, StreamYard, making CrewAI recompute ICP scores or Learner weights, hard dependency on the `cme.chp` package, merging PR 9’s `CREWAI_MODE` adapter (compose with it; do not replace it).
