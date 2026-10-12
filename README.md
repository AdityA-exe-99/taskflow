# TaskFlow

SWE40006 AeroDeploy project: Flask task manager deployed through a GitHub Actions
pipeline to Azure staging and production VMs, monitored with Prometheus and Grafana.

## Workflow
- Branch from main as feature/<name>
- Open a PR, get 1 review, merge when checks pass
- Merging to main runs .github/workflows/pipeline.yml automatically

## Shared values
- Image: ghcr.io/aditya-exe-99/taskflow:<commit-sha>
- App port: Gunicorn on 8000 (Nginx on 80 in production)
- Env vars: DATABASE_URL, SECRET_KEY, APP_VERSION