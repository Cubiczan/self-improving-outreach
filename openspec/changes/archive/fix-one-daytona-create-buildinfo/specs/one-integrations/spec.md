## ADDED Requirements

### Requirement: One Daytona create payload includes buildInfo

When creating a sandbox through One, `OneDaytonaClient.create` SHALL merge defaults so the execute `-d` body includes `buildInfo.dockerfileContent` even when the caller only passes `name` and/or `labels`. The body MAY also include `snapshot`. Defaults SHALL be overridable via `ONE_DAYTONA_DOCKERFILE` and `ONE_DAYTONA_SNAPSHOT`. Caller-supplied `buildInfo` and `snapshot` SHALL win. Execute SHALL NOT rely on `--skip-validation` as the only way to satisfy One’s create-sandbox schema. Tests SHALL mock the CLI (no live One).

#### Scenario: Name-only create satisfies One schema

- GIVEN One Daytona ready
- WHEN `create({"name": "cubiczan-outreach"})` runs
- THEN the execute `-d` body SHALL contain `buildInfo.dockerfileContent`
- AND the body MAY contain `snapshot`
- AND the execute command SHALL NOT pass `--skip-validation`

#### Scenario: Caller buildInfo and snapshot win

- GIVEN a create call with explicit `buildInfo.dockerfileContent` and `snapshot`
- WHEN defaults are merged
- THEN the execute body SHALL keep the caller Dockerfile and snapshot
