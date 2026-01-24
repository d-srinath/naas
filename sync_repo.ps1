# Sync script for naas repo - downloads all files from GitHub (PowerShell)
# Usage: .\sync_repo.ps1 [-TargetDir <path>]
#
# This script downloads all source files from the GitHub repo.
# Run it whenever you want to get the latest version.

param(
    [string]$TargetDir = "."
)

$ErrorActionPreference = "Stop"

$Repo = "d-srinath/naas"
$Branch = "main"
$BaseUrl = "https://raw.githubusercontent.com/$Repo/$Branch"

Write-Host "Syncing naas repo to: $TargetDir"

# Create directories
$Dirs = @(
    "$TargetDir",
    "$TargetDir/charts/namespace-onboarding/templates",
    "$TargetDir/input/team-a",
    "$TargetDir/input/team-test-one",
    "$TargetDir/input/team-test-two",
    "$TargetDir/scripts"
)

foreach ($dir in $Dirs) {
    if (!(Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}

# Files to download
$Files = @(
    "CLAUDE.md",
    "PROBLEM_STATEMENT.md",
    "README.md",
    "REQUIREMENTS.md",
    "TREE.md",
    "charts/namespace-onboarding/Chart.yaml",
    "charts/namespace-onboarding/values.yaml",
    "charts/namespace-onboarding/templates/application.yaml",
    "charts/namespace-onboarding/templates/appproject.yaml",
    "charts/namespace-onboarding/templates/namespace.yaml",
    "charts/namespace-onboarding/templates/resourcequota.yaml",
    "charts/namespace-onboarding/templates/rolebinding.yaml",
    "input/team-a/project.properties",
    "input/team-a/team-a-dev-quotas.yml",
    "input/team-a/team-a-prod-quotas.yml",
    "input/team-test-one/project.properties",
    "input/team-test-one/team-test-one-dev-quotas.yml",
    "input/team-test-one/team-test-one-prod-quotas.yml",
    "input/team-test-two/project.properties",
    "input/team-test-two/team-test-two-stage-quotas.yml",
    "scripts/convert_all.py"
)

foreach ($file in $Files) {
    Write-Host "Downloading: $file"
    $url = "$BaseUrl/$file"
    $outPath = "$TargetDir/$file"
    Invoke-WebRequest -Uri $url -OutFile $outPath -UseBasicParsing
}

Write-Host ""
Write-Host "Done! Files synced to: $TargetDir"
Write-Host "Run: python3 scripts/convert_all.py"
