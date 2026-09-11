# Design

## Circular import

Verified cycle:

`tools/__init__.py` (eager You.com) → `you_com` → `stores.base` → `chp.models` (loads `chp/__init__.py`) → `chp.session` → `OutreachStore` while `stores.base` is incomplete.

Fix: lazy package exports on `tools` and `chp`; `TYPE_CHECKING` for `ChpDecision` / You.com store+tracer types. No store or CHP behavior change.

## SDK region

Daytona Python SDK: `DaytonaConfig(target="us")` and env `DAYTONA_TARGET`. `DAYTONA_REGION` is an alias. Passed only when set so a dashboard org default still works.

## OTEL

Default OTLP HTTP is `localhost:4318`. Probe loopback with a short TCP timeout; if down, pass `otel_enabled=False` and emit `daytona.otel_disabled`. Local `LoggingTracer` spans are unchanged.
