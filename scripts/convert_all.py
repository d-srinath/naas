#!/usr/bin/env python3
"""
Convert legacy team configs (project.properties + *-quotas.yml) into Helm values YAML per env.

Input:
  input/<team>/
    - project.properties
    - <team>-<env>-quotas.yml (1..N)

Output:
  output/<team>/<env>.yaml
"""

from __future__ import annotations
import sys
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple
import argparse

import yaml


# ----------------------------
# CONFIG (edit as needed)
# ----------------------------
DEFAULT_INPUT_ROOT = Path("input")
DEFAULT_OUTPUT_ROOT = Path("output")

# explicit 1:1 mapping from properties keys to Helm values keys
# Output keys support dot-notation for nesting.
KEY_MAP = {
    "PROJECT_DOMAIN": "project.domain",
    "PROJECT_MANAGER": "project.manager",
    "PROJECT_CODE": "project.code",
    "PROJECT_COST_CENTER": "project.cost_center",
    "CREATED_DATE": "project.create_date",
    "CREATED_BY": "project.created_by",
    "CMDB_APPLICATION": "project.cmdb_application",
    "AD_GROUP": "adgroup",
    "REQUEST_ID": "request_id",
}

# namespace format (make configurable if needed)
DEFAULT_NAMESPACE_FMT = "{team}-{env}-1"

# filename pattern: <team>-<env>-quotas.yml
QUOTA_RE = re.compile(r"^(?P<team>.+)-(?P<env>[^-]+)-quotas\.ya?ml$")

# Kubernetes namespace validation regex (RFC 1123 label)
NAMESPACE_RE = re.compile(r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?$')


# ----------------------------
# Helpers
# ----------------------------
def set_nested(d: Dict[str, Any], dotted_key: str, value: Any) -> None:
    parts = dotted_key.split(".")
    cur = d
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value


def parse_properties(path: Path) -> Dict[str, Any]:
    """
    Read KEY=VALUE lines, skip blanks and comments.
    Apply KEY_MAP and build nested dict.
    """
    out: Dict[str, Any] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip()
        if k in KEY_MAP:
            set_nested(out, KEY_MAP[k], v)
    return out


def extract_resource_quota(quota_doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract ResourceQuota.spec.hard and convert to Helm structure.

    Input quota_doc is expected to be either:
      - a Template-like object with `objects: [...]`
      - OR a plain ResourceQuota object
    """
    rq_obj = None

    if isinstance(quota_doc, dict) and quota_doc.get("kind") == "ResourceQuota":
        rq_obj = quota_doc
    else:
        for obj in quota_doc.get("objects", []):
            if isinstance(obj, dict) and obj.get("kind") == "ResourceQuota":
                rq_obj = obj
                break

    if not rq_obj:
        raise ValueError("No ResourceQuota object found in quota YAML")

    hard = rq_obj.get("spec", {}).get("hard", {}) or {}

    def hard_str(key: str) -> str:
        val = hard.get(key, "")
        return "" if val is None else str(val)

    # Build chart-compatible values
    out = {
        "enabled": True,
        "cpu": {
            "requests": hard_str("requests.cpu"),
            "limits": hard_str("limits.cpu"),
        },
        "memory": {
            "requests": hard_str("requests.memory"),
            "limits": hard_str("limits.memory"),
        },
        "storage": hard_str("requests.storage"),
        "pods": hard_str("pods"),
    }

    # remove empty pods if not set
    if not out["pods"]:
        out.pop("pods", None)

    return out


def validate_namespace(namespace: str) -> Tuple[bool, str]:
    """
    Validate namespace against Kubernetes naming rules (RFC 1123 label).
    Returns (is_valid, error_message).
    """
    if not namespace:
        return False, "namespace is empty"
    if len(namespace) > 63:
        return False, f"namespace too long ({len(namespace)} chars, max 63)"
    if not NAMESPACE_RE.match(namespace):
        return False, "invalid characters (must be lowercase alphanumeric or '-', start/end with alphanumeric)"
    return True, ""


def convert_team(
    team_dir: Path,
    output_root: Path,
    namespace_fmt: str,
    errors: List[Tuple[str, str]],
) -> int:
    """
    Convert a team's config files to Helm values.
    Returns count of successfully converted namespaces.
    Appends errors to the errors list instead of stopping.
    """
    team = team_dir.name
    success_count = 0

    props_path = team_dir / "project.properties"
    if not props_path.exists():
        errors.append((f"{team}", "missing project.properties"))
        print(f"SKIP {team}: missing project.properties")
        return 0

    try:
        team_props = parse_properties(props_path)
    except Exception as e:
        errors.append((f"{team}", f"failed to parse project.properties: {e}"))
        print(f"SKIP {team}: failed to parse project.properties: {e}")
        return 0

    out_dir = output_root / team
    out_dir.mkdir(parents=True, exist_ok=True)

    quota_files = sorted(team_dir.glob("*-quotas.y*ml"))
    if not quota_files:
        errors.append((f"{team}", "no quota files found"))
        print(f"SKIP {team}: no quota files found")
        return 0

    for qf in quota_files:
        m = QUOTA_RE.match(qf.name)
        if not m:
            errors.append((f"{team}/{qf.name}", "quota filename not recognized"))
            print(f"WARN {team}: quota filename not recognized: {qf.name}")
            continue
        env = m.group("env")
        ns_id = f"{team}/{env}"

        try:
            namespace = namespace_fmt.format(team=team, env=env)
        except Exception as e:
            errors.append((ns_id, f"failed to format namespace: {e}"))
            print(f"FAIL {ns_id}: failed to format namespace: {e}")
            continue

        # Validate namespace name
        is_valid, validation_error = validate_namespace(namespace)
        if not is_valid:
            errors.append((ns_id, f"invalid namespace '{namespace}': {validation_error}"))
            print(f"FAIL {ns_id}: invalid namespace '{namespace}': {validation_error}")
            continue

        try:
            doc = yaml.safe_load(qf.read_text())
        except Exception as e:
            errors.append((ns_id, f"failed to parse quota YAML: {e}"))
            print(f"FAIL {ns_id}: failed to parse quota YAML: {e}")
            continue

        try:
            resource_quota = extract_resource_quota(doc)
        except Exception as e:
            errors.append((ns_id, f"failed to extract ResourceQuota: {e}"))
            print(f"FAIL {ns_id}: failed to extract ResourceQuota: {e}")
            continue

        values = {
            "team": team,
            "namespace": namespace,
            "project": {
                "domain": "",
                "manager": "",
                "code": "",
                "cost_center": "",
                "create_date": "",
                "created_by": "",
                "cmdb_application": "",
            },
            "adgroup": "",
            "request_id": "",
            "repositories": [],
            "applications": [],
            "resourceQuota": {
                "enabled": False,
                "cpu": {"requests": "", "limits": ""},
                "memory": {"requests": "", "limits": ""},
                "storage": "",
            },
        }

        # merge mapped properties
        # (team_props already has nested structure)
        def deep_merge(dst: Dict[str, Any], src: Dict[str, Any]) -> Dict[str, Any]:
            for k, v in src.items():
                if isinstance(v, dict) and isinstance(dst.get(k), dict):
                    deep_merge(dst[k], v)
                else:
                    dst[k] = v
            return dst

        deep_merge(values, team_props)

        # set extracted quota
        values["resourceQuota"] = resource_quota

        try:
            out_file = out_dir / f"{env}.yaml"
            out_file.write_text(yaml.safe_dump(values, sort_keys=False))
            print(f"OK   {ns_id} -> {out_file}")
            success_count += 1
        except Exception as e:
            errors.append((ns_id, f"failed to write output file: {e}"))
            print(f"FAIL {ns_id}: failed to write output file: {e}")
            continue

    return success_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert legacy team configs to Helm values files.",
    )
    parser.add_argument(
        "--input-root",
        type=Path,
        default=DEFAULT_INPUT_ROOT,
        help="Root directory containing team folders (default: input).",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Root directory to write converted values (default: output).",
    )
    parser.add_argument(
        "--namespace-format",
        default=DEFAULT_NAMESPACE_FMT,
        help="Namespace format string (default: '{team}-{env}-1').",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_root = args.input_root
    output_root = args.output_root
    namespace_fmt = args.namespace_format

    if not input_root.exists():
        print(f"ERROR: input root not found: {input_root}")
        return 2

    output_root.mkdir(parents=True, exist_ok=True)

    team_dirs = [p for p in input_root.iterdir() if p.is_dir()]
    if not team_dirs:
        print(f"ERROR: no team directories under {input_root}")
        return 2

    # Track errors and success counts
    errors: List[Tuple[str, str]] = []
    total_success = 0

    for td in sorted(team_dirs):
        total_success += convert_team(td, output_root, namespace_fmt, errors)

    # Print summary
    print("")
    print("=" * 60)
    print(f"SUMMARY: {total_success} namespace(s) converted successfully")
    print(f"         {len(errors)} error(s) encountered")
    print("=" * 60)

    if errors:
        print("")
        print("PROBLEMATIC NAMESPACES:")
        print("-" * 60)
        for ns_id, error_msg in errors:
            print(f"  {ns_id}")
            print(f"    -> {error_msg}")
        print("-" * 60)
        print(f"Total: {len(errors)} issue(s) to fix")
        print("")
        # Return 1 if there were errors but some succeeded, 2 if all failed
        return 1 if total_success > 0 else 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
