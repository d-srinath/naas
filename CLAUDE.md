# CLAUDE.md

This file provides guidance for Claude Code when working with this repository.

## Project Overview

Namespace-as-a-Service (NaaS) automation that converts legacy team configurations into Helm values files for Kubernetes namespace provisioning. The system creates Namespace, ResourceQuota, RBAC, and ArgoCD resources.

## Quick Commands

```bash
# Install dependencies
python3 -m pip install pyyaml

# Run the conversion script (uses defaults: input/ -> output/)
python3 scripts/convert_all.py

# Run with custom paths and namespace format
python3 scripts/convert_all.py --input-root /path/to/input --output-root /path/to/output --namespace-format "{team}-{env}-ns"

# Validate Helm chart
helm lint charts/namespace-onboarding

# Template chart with values
helm template ns charts/namespace-onboarding -f output/<team>/<env>.yaml
```

## Project Structure

- `scripts/convert_all.py` - Main conversion script (Python 3)
- `charts/namespace-onboarding/` - Helm chart for namespace provisioning
- `input/<team>/` - Legacy config files per team
- `output/<team>/` - Generated Helm values files

## Input Format

Each team directory in `input/` contains:
- `project.properties` - KEY=VALUE metadata (PROJECT_DOMAIN, AD_GROUP, etc.)
- `<team>-<env>-quotas.yml` - ResourceQuota specs per environment

## Key Configuration

In `scripts/convert_all.py`:
- `KEY_MAP` (lines 32-42) - Maps properties keys to Helm values paths
- `DEFAULT_NAMESPACE_FMT` - Default namespace pattern: `{team}-{env}-1`
- `QUOTA_RE` - Regex for parsing quota filenames

### CLI Options
- `--input-root` - Input directory (default: `input/`)
- `--output-root` - Output directory (default: `output/`)
- `--namespace-format` - Namespace naming pattern (default: `{team}-{env}-1`)

## Development Guidelines

- Use `yaml.safe_load()` for parsing YAML
- Use `yaml.safe_dump(data, sort_keys=False)` for output
- Support both Template wrapper and direct ResourceQuota objects
- Dot-notation in KEY_MAP creates nested structures (e.g., `project.domain`)

## Helm Chart Values

Key values in `charts/namespace-onboarding/values.yaml`:
- `team`, `namespace` - Identifiers
- `project.*` - Metadata (domain, manager, code, cost_center)
- `adgroup` - LDAP/AD group for admin access
- `resourceQuota.*` - CPU, memory, storage limits
- `repositories`, `applications` - ArgoCD configuration
