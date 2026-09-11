# Design

## Queue reclaim

`requeue_leads` on the store (ClickHouse or memory / JSON queue):

| Selector | Behavior |
| --- | --- |
| `--lead-id` (repeatable) | Set those rows to `queued`; if missing, resolve from `data/leads.sample.json` |
| `--company` | Case-insensitive substring match |
| `--all-sample` | Upsert the committed sample ICP leads as `queued` |
| `--clear-processing` | Set `processing` → `queued` (stuck workers) |

`--queue` points at a persistable JSON file. The committed sample file is never overwritten.

## Learn on draft

Today mock mode with `SIMULATE_OUTCOMES=true` already simulates after draft so CI can show weights/patterns move. Live (`MOCK_MODE=false`) must **not** invent outcomes unless `LEARN_ON_DRAFT=true`.

```
should_learn_on_draft = LEARN_ON_DRAFT or (SIMULATE_OUTCOMES and is_mock)
```

Production default: `LEARN_ON_DRAFT=false`. Scout still reports `thumbs_up` / `thumbs_down` / `replied` / `meeting` / `ignore` / `sent` through `learn`.

## LiveKit auto

Unchanged contract: `LIVEKIT_FEEDBACK_AUTO=true` + `LIVEKIT_TRANSCRIPT_PATH` after a successful draft. Keys are only for a live room. Default false. Core text crew does not import LiveKit at import time.

## ClickUp ingest

`lead_from_clickup` unwraps `{task: ...}` webhook envelopes and ClickUp task objects. Maps `id` → `clickup-{id}` (or explicit `lead_id`), custom fields (company / contact / title / industry / domain / location / pain), and task name `Company — Contact`. Ingests only when status is `Queued` unless `--force`. No ads destinations.
