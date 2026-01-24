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
from typing import Dict, Any

import yaml


# ----------------------------
# CONFIG (edit as needed)
# ----------------------------
INPUT_ROOT = Path("input")
OUTPUT_ROOT = Path("output")

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
NAMESPACE_FMT = "{team}-{env}-1"

# filename pattern: <team>-<env>-quotas.yml
QUOTA_RE = re.compile(r"^(?P<team>.+)-(?P<env>[^-]+)-quotas\.ya?ml$")


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


def convert_team(team_dir: Path) -> None:
    team = team_dir.name
    props_path = team_dir / "project.properties"
    if not props_path.exists():
        print(f"SKIP {team}: missing project.properties")
        return

    team_props = parse_properties(props_path)

    out_dir = OUTPUT_ROOT / team
    out_dir.mkdir(parents=True, exist_ok=True)

    quota_files = sorted(team_dir.glob("*-quotas.y*ml"))
    if not quota_files:
        print(f"SKIP {team}: no quota files found")
        return

    for qf in quota_files:
        m = QUOTA_RE.match(qf.name)
        if not m:
            print(f"WARN {team}: quota filename not recognized: {qf.name}")
            continue
        env = m.group("env")

        namespace = NAMESPACE_FMT.format(team=team, env=env)

        doc = yaml.safe_load(qf.read_text())
        resource_quota = extract_resource_quota(doc)

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

        out_file = out_dir / f"{env}.yaml"
        out_file.write_text(yaml.safe_dump(values, sort_keys=False))
        print(f"OK  {team}/{env} -> {out_file}")


def main() -> int:
    if not INPUT_ROOT.exists():
        print(f"ERROR: input root not found: {INPUT_ROOT}")
        return 2

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    team_dirs = [p for p in INPUT_ROOT.iterdir() if p.is_dir()]
    if not team_dirs:
        print(f"ERROR: no team directories under {INPUT_ROOT}")
        return 2

    for td in sorted(team_dirs):
        convert_team(td)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
