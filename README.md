# naas
Namespace as Service helm chart and argocd
# namespace-config-to-helm-values

This repo contains:
- A Helm chart (`charts/namespace-onboarding`) that creates Namespace, ResourceQuota, RBAC, and optional Argo objects.
- A script (`scripts/convert_all.py`) that converts legacy configs:
  - `project.properties`
  - `<team>-<env>-quotas.yml`
into Helm values files per team/env under `output/`.

## Run
```bash
python3 -m pip install pyyaml
python3 scripts/convert_all.py

# Optional overrides
# python3 scripts/convert_all.py --input-root input --output-root output --namespace-format "{team}-{env}-1"
