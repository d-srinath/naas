# Requirements

## Functional
- Discover all team directories under a configurable root folder (e.g. `input/`).
- For each team directory:
  - Read `project.properties`.
  - Read every `*-quotas.yml` file in that directory.
  - Derive `env` from file name: `<team>-<env>-quotas.yml`
  - Derive namespace name: `<team>-<env>-1` (can be made configurable).
  - Extract ResourceQuota.spec.hard into Helm values format.

## Key mapping and normalization
- Properties keys are in UPPER_SNAKE_CASE. Output keys are lower_snake_case nested under `project` except a few top-level keys.
- Must support explicit 1:1 mapping (old key → new key).

## Output
- Write output under `output/<team>/<env>.yaml`.
- Values must include:
  - team
  - namespace
  - project (dict)
  - adgroup (string)
  - request_id (string)
  - repositories: []
  - applications: []
  - resourceQuota (dict)
- Do NOT include any organization/company names in repo content.

## Non-functional
- Deterministic output.
- Read-only input (no mutation).
- Clear error messages for missing files.
