# Daytona live retest — 2026-09-11 (US)

Architecture / integration smoke test. Not live outreach metrics.

## Setup
- Provider: Daytona SDK (`SANDBOX_PROVIDER=daytona`)
- `DAYTONA_SANDBOX_RUNS=true`
- `DAYTONA_TARGET=us` (org default region also set to `us` in Daytona Dashboard)
- `DAYTONA_OTEL_ENABLED=false` (no Grafana/OTLP collector wired yet)
- Branch under test at retest time: `cursor/fix-daytona-import-region-0512`

## Result: PASS

| Step | Outcome |
| --- | --- |
| `daytona.client_ready` | OK — `https://app.daytona.io/api`, target `us` |
| Sandbox create | OK — id `c481c256-742a-47a2-93a2-516750c96a9b` |
| `daytona.sandbox_created` | OK |
| `code_run` | OK — printed `cubiczan-daytona-ok` (exit 0) |
| Sandbox delete | OK |

## Probe JSON
See `live-retest-2026-09-11.json` in this folder (sanitized span events only).

## Notes
- Earlier failure (“organization does not have a default region”) cleared after Dashboard default region = `us` + `DAYTONA_TARGET=us`.
- Leave Daytona org OTLP blank until a real Grafana Cloud OTLP endpoint is configured (do not use `otel-collector.example.com`).
- One Daytona path circular-import fix is tracked separately in PR #11; this document is the **live test record**, not the code change.
