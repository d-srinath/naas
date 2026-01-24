#!/usr/bin/env python3
"""
Tests for convert_all.py - validates quota extraction, property parsing, and output generation.

Run with: pytest scripts/test_convert_all.py -v
"""

import pytest
import tempfile
import shutil
from pathlib import Path

from convert_all import (
    parse_properties,
    extract_resource_quota,
    extract_limit_range,
    validate_namespace,
    set_nested,
    convert_team,
)


class TestSetNested:
    """Tests for set_nested helper function."""

    def test_single_level(self):
        d = {}
        set_nested(d, "key", "value")
        assert d == {"key": "value"}

    def test_two_levels(self):
        d = {}
        set_nested(d, "project.domain", "engineering")
        assert d == {"project": {"domain": "engineering"}}

    def test_three_levels(self):
        d = {}
        set_nested(d, "a.b.c", "deep")
        assert d == {"a": {"b": {"c": "deep"}}}

    def test_existing_structure(self):
        d = {"project": {"existing": "value"}}
        set_nested(d, "project.new", "added")
        assert d == {"project": {"existing": "value", "new": "added"}}


class TestParseProperties:
    """Tests for parsing project.properties files."""

    def test_basic_parsing(self, tmp_path):
        props_file = tmp_path / "project.properties"
        props_file.write_text("""
PROJECT_DOMAIN=engineering
PROJECT_MANAGER=John Doe
AD_GROUP=TEAM-ADMINS
""")
        result = parse_properties(props_file)
        assert result == {
            "project": {
                "domain": "engineering",
                "manager": "John Doe",
            },
            "adgroup": "TEAM-ADMINS",
        }

    def test_all_fields(self, tmp_path):
        props_file = tmp_path / "project.properties"
        props_file.write_text("""
PROJECT_DOMAIN=demo
PROJECT_MANAGER=Manager
PROJECT_CODE=APP1001
PROJECT_COST_CENTER=1001
CREATED_DATE=2025-01-01
CREATED_BY=Automation
CMDB_APPLICATION=MyApp
AD_GROUP=ADMINS
REQUEST_ID=REQ-123
""")
        result = parse_properties(props_file)
        assert result["project"]["domain"] == "demo"
        assert result["project"]["manager"] == "Manager"
        assert result["project"]["code"] == "APP1001"
        assert result["project"]["cost_center"] == "1001"
        assert result["project"]["create_date"] == "2025-01-01"
        assert result["project"]["created_by"] == "Automation"
        assert result["project"]["cmdb_application"] == "MyApp"
        assert result["adgroup"] == "ADMINS"
        assert result["request_id"] == "REQ-123"

    def test_comments_ignored(self, tmp_path):
        props_file = tmp_path / "project.properties"
        props_file.write_text("""
# This is a comment
PROJECT_DOMAIN=test
# Another comment
AD_GROUP=GROUP
""")
        result = parse_properties(props_file)
        assert result == {
            "project": {"domain": "test"},
            "adgroup": "GROUP",
        }

    def test_empty_lines_ignored(self, tmp_path):
        props_file = tmp_path / "project.properties"
        props_file.write_text("""

PROJECT_DOMAIN=test

AD_GROUP=GROUP

""")
        result = parse_properties(props_file)
        assert len(result) == 2

    def test_unknown_keys_ignored(self, tmp_path):
        props_file = tmp_path / "project.properties"
        props_file.write_text("""
PROJECT_DOMAIN=test
UNKNOWN_KEY=ignored
ANOTHER_UNKNOWN=also_ignored
AD_GROUP=GROUP
""")
        result = parse_properties(props_file)
        assert "UNKNOWN_KEY" not in str(result)
        assert result["project"]["domain"] == "test"


class TestExtractResourceQuota:
    """Tests for extracting ResourceQuota from YAML documents."""

    def test_template_wrapper(self):
        doc = {
            "apiVersion": "v1",
            "kind": "Template",
            "objects": [
                {
                    "apiVersion": "v1",
                    "kind": "ResourceQuota",
                    "metadata": {"name": "quota"},
                    "spec": {
                        "hard": {
                            "requests.cpu": "2",
                            "limits.cpu": "4",
                            "requests.memory": "8Gi",
                            "limits.memory": "16Gi",
                            "requests.storage": "10Gi",
                            "pods": "50",
                        }
                    },
                }
            ],
        }
        result = extract_resource_quota(doc)
        assert result["enabled"] is True
        assert result["cpu"]["requests"] == "2"
        assert result["cpu"]["limits"] == "4"
        assert result["memory"]["requests"] == "8Gi"
        assert result["memory"]["limits"] == "16Gi"
        assert result["storage"] == "10Gi"
        assert result["pods"] == "50"

    def test_plain_resource_quota(self):
        doc = {
            "apiVersion": "v1",
            "kind": "ResourceQuota",
            "metadata": {"name": "quota"},
            "spec": {
                "hard": {
                    "requests.cpu": "1",
                    "limits.cpu": "2",
                    "requests.memory": "4Gi",
                    "limits.memory": "8Gi",
                }
            },
        }
        result = extract_resource_quota(doc)
        assert result["enabled"] is True
        assert result["cpu"]["requests"] == "1"
        assert result["memory"]["limits"] == "8Gi"

    def test_no_pods_field(self):
        doc = {
            "kind": "ResourceQuota",
            "spec": {
                "hard": {
                    "requests.cpu": "1",
                    "limits.cpu": "2",
                }
            },
        }
        result = extract_resource_quota(doc)
        assert "pods" not in result

    def test_missing_quota_raises(self):
        doc = {"kind": "Template", "objects": []}
        with pytest.raises(ValueError, match="No ResourceQuota"):
            extract_resource_quota(doc)

    def test_numeric_values_converted_to_string(self):
        doc = {
            "kind": "ResourceQuota",
            "spec": {
                "hard": {
                    "requests.cpu": 2,  # numeric, not string
                    "limits.cpu": 4,
                    "pods": 100,
                }
            },
        }
        result = extract_resource_quota(doc)
        assert result["cpu"]["requests"] == "2"
        assert result["cpu"]["limits"] == "4"
        assert result["pods"] == "100"


class TestExtractLimitRange:
    """Tests for extracting LimitRange from YAML documents."""

    def test_single_limit_range(self):
        doc = {
            "kind": "Template",
            "objects": [
                {
                    "kind": "LimitRange",
                    "spec": {
                        "limits": [
                            {
                                "type": "Container",
                                "max": {"cpu": "2", "memory": "4Gi"},
                                "min": {"cpu": "100m", "memory": "128Mi"},
                                "default": {"cpu": "500m", "memory": "512Mi"},
                                "defaultRequest": {"cpu": "250m", "memory": "256Mi"},
                            }
                        ]
                    },
                }
            ],
        }
        result = extract_limit_range(doc)
        assert result["enabled"] is True
        assert result["container"]["maxCpu"] == "2"
        assert result["container"]["maxMemory"] == "4Gi"
        assert result["container"]["minCpu"] == "100m"
        assert result["container"]["defaultCpu"] == "500m"
        assert result["container"]["defaultRequestMemory"] == "256Mi"

    def test_multiple_limit_ranges_merged(self):
        """Test that memory-small and cpu-medium are merged."""
        doc = {
            "kind": "Template",
            "objects": [
                {
                    "kind": "LimitRange",
                    "metadata": {"name": "memory-small"},
                    "spec": {
                        "limits": [
                            {
                                "type": "Pod",
                                "max": {"memory": "4Gi"},
                                "min": {"memory": "64Mi"},
                            },
                            {
                                "type": "Container",
                                "max": {"memory": "4Gi"},
                                "min": {"memory": "64Mi"},
                                "default": {"memory": "500Mi"},
                                "defaultRequest": {"memory": "128Mi"},
                            },
                        ]
                    },
                },
                {
                    "kind": "LimitRange",
                    "metadata": {"name": "cpu-medium"},
                    "spec": {
                        "limits": [
                            {
                                "type": "Pod",
                                "max": {"cpu": "2"},
                                "min": {"cpu": "10m"},
                            },
                            {
                                "type": "Container",
                                "max": {"cpu": "2"},
                                "min": {"cpu": "5m"},
                                "default": {"cpu": "100m"},
                                "defaultRequest": {"cpu": "100m"},
                            },
                        ]
                    },
                },
            ],
        }
        result = extract_limit_range(doc)
        assert result["enabled"] is True

        # Pod limits merged
        assert result["pod"]["maxMemory"] == "4Gi"
        assert result["pod"]["minMemory"] == "64Mi"
        assert result["pod"]["maxCpu"] == "2"
        assert result["pod"]["minCpu"] == "10m"

        # Container limits merged
        assert result["container"]["maxMemory"] == "4Gi"
        assert result["container"]["maxCpu"] == "2"
        assert result["container"]["defaultMemory"] == "500Mi"
        assert result["container"]["defaultCpu"] == "100m"

    def test_no_limit_range_returns_disabled(self):
        doc = {"kind": "Template", "objects": []}
        result = extract_limit_range(doc)
        assert result["enabled"] is False

    def test_plain_limit_range_object(self):
        doc = {
            "kind": "LimitRange",
            "spec": {
                "limits": [
                    {"type": "Container", "max": {"cpu": "1"}}
                ]
            },
        }
        result = extract_limit_range(doc)
        assert result["enabled"] is True
        assert result["container"]["maxCpu"] == "1"


class TestValidateNamespace:
    """Tests for namespace validation."""

    def test_valid_namespace(self):
        is_valid, error = validate_namespace("my-namespace")
        assert is_valid is True
        assert error == ""

    def test_valid_with_numbers(self):
        is_valid, _ = validate_namespace("team-dev-1")
        assert is_valid is True

    def test_empty_namespace(self):
        is_valid, error = validate_namespace("")
        assert is_valid is False
        assert "empty" in error

    def test_too_long(self):
        is_valid, error = validate_namespace("a" * 64)
        assert is_valid is False
        assert "too long" in error

    def test_uppercase_invalid(self):
        is_valid, error = validate_namespace("MyNamespace")
        assert is_valid is False
        assert "invalid characters" in error

    def test_underscore_invalid(self):
        is_valid, error = validate_namespace("my_namespace")
        assert is_valid is False

    def test_starts_with_dash_invalid(self):
        is_valid, error = validate_namespace("-namespace")
        assert is_valid is False

    def test_ends_with_dash_invalid(self):
        is_valid, error = validate_namespace("namespace-")
        assert is_valid is False


class TestConvertTeam:
    """Integration tests for convert_team function."""

    def test_full_conversion(self, tmp_path):
        # Create input structure
        team_dir = tmp_path / "input" / "team-test"
        team_dir.mkdir(parents=True)

        # Create project.properties
        (team_dir / "project.properties").write_text("""
PROJECT_DOMAIN=engineering
PROJECT_MANAGER=Test Manager
AD_GROUP=TEAM-ADMINS
REQUEST_ID=REQ-001
""")

        # Create quota file
        (team_dir / "team-test-dev-quotas.yml").write_text("""
apiVersion: v1
kind: Template
objects:
  - apiVersion: v1
    kind: ResourceQuota
    spec:
      hard:
        requests.cpu: 2
        limits.cpu: 4
        requests.memory: 8Gi
        limits.memory: 16Gi
""")

        output_dir = tmp_path / "output"
        errors = []

        count = convert_team(team_dir, output_dir, "{team}-{env}-1", errors)

        assert count == 1
        assert len(errors) == 0

        # Verify output file exists and has correct content
        output_file = output_dir / "team-test" / "dev.yaml"
        assert output_file.exists()

        import yaml
        with open(output_file) as f:
            result = yaml.safe_load(f)

        assert result["team"] == "team-test"
        assert result["namespace"] == "team-test-dev-1"
        assert result["project"]["domain"] == "engineering"
        assert result["adgroup"] == "TEAM-ADMINS"
        assert result["resourceQuota"]["enabled"] is True
        assert result["resourceQuota"]["cpu"]["requests"] == "2"

    def test_missing_project_properties(self, tmp_path):
        team_dir = tmp_path / "team-missing"
        team_dir.mkdir(parents=True)
        (team_dir / "team-missing-dev-quotas.yml").write_text("kind: ResourceQuota")

        errors = []
        count = convert_team(team_dir, tmp_path / "output", "{team}-{env}-1", errors)

        assert count == 0
        assert len(errors) == 1
        assert "file not found" in errors[0][2]

    def test_invalid_namespace_format(self, tmp_path):
        team_dir = tmp_path / "Team_Invalid"
        team_dir.mkdir(parents=True)
        (team_dir / "project.properties").write_text("AD_GROUP=TEST")
        (team_dir / "Team_Invalid-dev-quotas.yml").write_text("""
kind: ResourceQuota
spec:
  hard:
    requests.cpu: 1
""")

        errors = []
        count = convert_team(team_dir, tmp_path / "output", "{team}-{env}-1", errors)

        assert count == 0
        assert len(errors) == 1
        assert "invalid namespace" in errors[0][2]


class TestGoldenFiles:
    """Golden file tests using actual input files."""

    def test_team_test_one_dev(self, tmp_path):
        """Test conversion of team-test-one dev environment."""
        # This test uses the actual input files
        input_dir = Path(__file__).parent.parent / "input" / "team-test-one"
        if not input_dir.exists():
            pytest.skip("Input files not available")

        output_dir = tmp_path / "output"
        errors = []

        count = convert_team(input_dir, output_dir, "{team}-{env}-1", errors)

        # Should convert both dev and prod
        assert count == 2
        assert len(errors) == 0

        # Verify dev output
        import yaml
        dev_file = output_dir / "team-test-one" / "dev.yaml"
        assert dev_file.exists()

        with open(dev_file) as f:
            result = yaml.safe_load(f)

        assert result["namespace"] == "team-test-one-dev-1"
        assert result["project"]["domain"] == "demo"
        assert result["project"]["cost_center"] == "1001"
        assert result["adgroup"] == "TEAM-TEST-ONE-ADMINS"
        assert result["resourceQuota"]["cpu"]["requests"] == "1"
        assert result["resourceQuota"]["cpu"]["limits"] == "2"
        assert result["resourceQuota"]["memory"]["requests"] == "2Gi"
        assert result["resourceQuota"]["pods"] == "20"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
