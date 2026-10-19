# Browser (E2E) tests

Owner: Abhinav (Test/Staging Engineer)

Playwright drives a real Chromium browser through TaskFlow the way a user would.
In the pipeline these run **on the staging VM against the newly deployed release**.
If any fail, the pipeline stops and **production is not deployed**.

| File | What it checks |
|---|---|
| `test_smoke.py` | `/health` reports app + DB OK; staging runs the exact commit under test (`/api/info` and footer); dashboard and navigation load |
| `test_task_flow.py` | Full journey: create project → add task (priority, due date) → edit status → delete task → delete project; an overdue open task shows on the dashboard |
| `test_validation.py` | Blank project name and blank task title are rejected by the server with an inline error, keeping what was typed |
| `test_demo_switch.py` | Fails only when the pipeline is run with **simulate_e2e_failure** ticked (presentation demo) |

Every test uses a unique `E2E xxxxxxxx` name and deletes its data afterwards, even if it fails.

## How it runs in the pipeline

1. `deploy-staging` deploys the new image to the staging VM and checks `/health`.
2. `deploy/run-staging-e2e.sh` copies this folder to `/opt/aerodeploy/e2e` on staging
   and runs `run.sh` there over SSH.
3. `run.sh` starts `mcr.microsoft.com/playwright/python` (browsers included) and runs pytest
   against `http://127.0.0.1:8000`, the app on the same VM, which isn't exposed publicly.
4. JUnit results and failure traces are copied back and uploaded as the `e2e-results-<run>` artifact.

## Run locally (Mac/Windows with Docker Desktop)

```bash
cp .env.example .env        # set POSTGRES_PASSWORD and SECRET_KEY
docker compose -p aerodeploy-taskflow up --build --wait
E2E_NETWORK=bridge BASE_URL=http://host.docker.internal:8000 bash tests/e2e/run.sh
```

## Demo: failing test stops production

Actions → Pipeline → **Run workflow** → tick **simulate_e2e_failure** → Run.
Staging deploys, the browser tests fail, `deploy-prod` is skipped, and the live site
still shows the previous version in its footer.

To view a failure trace: download the artifact, then `npx playwright show-trace results/traces/<test>/trace.zip`.
