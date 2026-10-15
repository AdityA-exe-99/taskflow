# TaskFlow

![Pipeline](https://github.com/AdityA-exe-99/taskflow/actions/workflows/pipeline.yml/badge.svg)

SWE40006 Software Deployment and Evolution, group project (**AeroDeploy**).

TaskFlow is a small Flask + PostgreSQL task manager. The point of the project is the
pipeline around it: every merge to `main` is tested, built into a Docker image, deployed
to staging and production on Azure, and monitored with Prometheus and Grafana.

## Pipeline

```
Developer → PR (review + tests) → merge to main
  → CI/Build VM (self-hosted GitHub Actions runner)
      tests + 80% coverage gate → build image → push to GHCR (tagged with commit SHA)
  → Test/Staging VM: deploy same image, run integration + E2E tests
  → Production VM: deploy same image, health check, rollback on failure
  → Prometheus + Grafana monitoring
```

| Environment | Where | Owner |
|---|---|---|
| Code repository | GitHub (protected `main`, CODEOWNERS) | Aditya |
| CI/Build | Azure VM `ci-build-vm`, self-hosted runner | Aditya |
| Test/Staging | Azure VM, Docker Compose | Abhinav |
| Production | Azure VM `aerodeploy-prod`, Nginx, Docker Compose | Unna |
| Application | Flask app, Dockerfile, unit/integration tests | Mohita |

## Repository layout

| Path | Contents |
|---|---|
| `app/` | Flask application (models, views, templates, static) |
| `migrations/` | Database migrations (run automatically on container start) |
| `tests/unit`, `tests/integration`, `tests/e2e` | Automated tests |
| `deploy/` | Server compose file used on staging and production |
| `.github/workflows/pipeline.yml` | CI/CD pipeline |
| `scripts/` | Helper scripts (local test runner) |
| `docs/` | Handover and setup notes |
| `evidence/` | Screenshots and logs for the final report |
| `Dockerfile`, `docker-compose.yml` | App image and local development stack |
| `Dockerfile.test`, `docker-compose.test.yml` | Isolated test stack |

## Run locally

Requires Docker Desktop.

```powershell
Copy-Item .env.example .env      # then set POSTGRES_PASSWORD and SECRET_KEY
docker compose -p aerodeploy-taskflow up --build --wait
```

Open http://localhost:8000. Health: `/health`, metrics: `/metrics`.

Run the tests:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Test-TaskFlow.ps1
```

## Shared values

| Thing | Value |
|---|---|
| Image | `ghcr.io/aditya-exe-99/taskflow:<commit-sha>` |
| App port | Gunicorn on `8000` in the container; Nginx on `80` in production |
| Env vars | `DATABASE_URL` (built from `POSTGRES_PASSWORD`), `SECRET_KEY`, `APP_VERSION` (commit SHA) |
| Health check | `/health` returns `200 {"db":"ok","status":"ok"}`, or `503` |
| Metrics | `/metrics` (prometheus-flask-exporter) |

## Contributing

1. Branch from `main` as `feature/<name>`
2. Open a pull request; the pipeline runs the tests on the CI VM
3. A code owner reviews and merges
4. The merge to `main` triggers the build and deployment

Never commit `.env` or any credentials; secrets live in GitHub Actions secrets.
