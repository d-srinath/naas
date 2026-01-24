# Problem Statement: Convert legacy namespace configs into Helm values.yaml per namespace

We have a repository containing multiple "team folders" under a single root directory.

Each team folder contains:
1) A `project.properties` file in `KEY=VALUE` format (team-level common metadata).
2) One or more environment-specific YAML files (elastic count), e.g.
   - `<team>-prod-quotas.yml`
   - `<team>-stage-quotas.yml`
   - `<team>-test-quotas.yml`
   - `<team>-unit-quotas.yml`

Each environment YAML contains Kubernetes objects such as:
- ResourceQuota
- LimitRange
(typically wrapped in a single YAML structure that lists `objects`)

Goal:
For each team + environment, generate a Helm-compatible `values.yaml` file by merging:
- Mapped/renamed key-values from `project.properties`
- Quota values extracted from the ResourceQuota object in the env YAML

Constraints:
- Team name comes from the team folder name.
- Environment name comes from the quota YAML filename.
- Output should be organized per team, one values file per environment.

Helm chart:
- A Helm chart exists that expects values with these top-level keys:
  - team
  - namespace
  - project: (nested metadata, lower_snake_case keys)
  - adgroup
  - request_id
  - repositories (list)
  - applications (list)
  - resourceQuota (enabled + cpu/memory/storage + optional pods)

The generated values files must match the chart's expected structure.
