#!/bin/bash
# Sync script for naas repo - downloads all files from GitHub
# Usage: bash sync_repo.sh [target_directory]
#
# This script downloads all source files from the GitHub repo.
# Run it whenever you want to get the latest version.

set -e

REPO="d-srinath/naas"
BRANCH="main"
BASE_URL="https://raw.githubusercontent.com/${REPO}/${BRANCH}"
TARGET_DIR="${1:-.}"

echo "Syncing naas repo to: $TARGET_DIR"

# Create directories
mkdir -p "$TARGET_DIR"
mkdir -p "$TARGET_DIR/charts/namespace-onboarding/templates"
mkdir -p "$TARGET_DIR/input/team-a"
mkdir -p "$TARGET_DIR/input/team-test-one"
mkdir -p "$TARGET_DIR/input/team-test-two"
mkdir -p "$TARGET_DIR/scripts"

# Download files
FILES=(
    "CLAUDE.md"
    "PROBLEM_STATEMENT.md"
    "README.md"
    "REQUIREMENTS.md"
    "TREE.md"
    "charts/namespace-onboarding/Chart.yaml"
    "charts/namespace-onboarding/values.yaml"
    "charts/namespace-onboarding/templates/application.yaml"
    "charts/namespace-onboarding/templates/appproject.yaml"
    "charts/namespace-onboarding/templates/namespace.yaml"
    "charts/namespace-onboarding/templates/resourcequota.yaml"
    "charts/namespace-onboarding/templates/rolebinding.yaml"
    "input/team-a/project.properties"
    "input/team-a/team-a-dev-quotas.yml"
    "input/team-a/team-a-prod-quotas.yml"
    "input/team-test-one/project.properties"
    "input/team-test-one/team-test-one-dev-quotas.yml"
    "input/team-test-one/team-test-one-prod-quotas.yml"
    "input/team-test-two/project.properties"
    "input/team-test-two/team-test-two-stage-quotas.yml"
    "scripts/convert_all.py"
)

for file in "${FILES[@]}"; do
    echo "Downloading: $file"
    curl -sL "${BASE_URL}/${file}" -o "$TARGET_DIR/$file"
done

echo ""
echo "Done! Files synced to: $TARGET_DIR"
echo "Run: python3 scripts/convert_all.py"
