# Suggested repo layout

namespace-config-to-helm-values/
├── charts/
│   └── namespace-onboarding/
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
│           ├── namespace.yaml
│           ├── appproject.yaml
│           ├── resourcequota.yaml
│           ├── rolebinding.yaml
│           └── application.yaml
├── input/
│   ├── team-a/
│   │   ├── project.properties
│   │   ├── team-a-dev-quotas.yml
│   │   └── team-a-prod-quotas.yml
│   └── team-b/
│       ├── project.properties
│       └── team-b-test-quotas.yml
├── output/                 (generated)
├── scripts/
│   └── convert_all.py
├── PROBLEM_STATEMENT.md
├── REQUIREMENTS.md
└── README.md