# Design

## Root cause

`OneDaytonaClient.create` sent the caller dict as `-d` and set `skip_validation=not body`. The tracer always passes `{"name": "cubiczan-outreach-..."}`, so One validates the body against the create-sandbox schema and rejects it without `buildInfo.dockerfileContent`.

Daytona’s native `POST /sandbox` accepts either `snapshot` (example `ubuntu-4vcpu-8ram-100gb`) or `buildInfo`. One lists `buildInfo` as required, so the default payload always includes a Dockerfile. Snapshot is also sent by default so a snapshot-capable org can use it; operators can blank `ONE_DAYTONA_SNAPSHOT` to omit it.

## Defaults

| Field | Default | Env override |
| --- | --- | --- |
| `buildInfo.dockerfileContent` | `FROM daytonaio/sandbox:latest` | `ONE_DAYTONA_DOCKERFILE` |
| `snapshot` | `ubuntu-4vcpu-8ram-100gb` | `ONE_DAYTONA_SNAPSHOT` (empty omits) |

`merge_sandbox_create_body` deep-merges caller data over those defaults. Caller `buildInfo.dockerfileContent` and `snapshot` win. After merge, execute runs **without** `--skip-validation`.

## Tests

Inspect the mocked `one --agent actions execute ... -d` JSON. No live One.
