#!/bin/bash
# Runs the browser (E2E) tests inside the official Playwright image, so the
# machine only needs Docker. Exit code is non-zero if any test fails.
#
# On the staging VM (the pipeline does this for you):
#   bash /opt/aerodeploy/e2e/run.sh <expected-version>
# On your own computer, against a local copy of the app on port 8000:
#   E2E_NETWORK=bridge BASE_URL=http://host.docker.internal:8000 bash tests/e2e/run.sh
#
# Owner: Abhinav (Test/Staging)
set -euo pipefail
cd "$(dirname "$0")"

EXPECTED_VERSION="${1:-}"
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
NETWORK="${E2E_NETWORK:-host}"
SIMULATE_FAILURE="${E2E_SIMULATE_FAILURE:-false}"
# Must match the playwright version in requirements-e2e.txt
IMAGE="mcr.microsoft.com/playwright/python:v1.63.0-noble"

mkdir -p results
echo "Running browser tests against $BASE_URL (expected version: ${EXPECTED_VERSION:-any})"

docker run --rm --network "$NETWORK" --ipc=host \
  --user "$(id -u):$(id -g)" -e HOME=/tmp -e PIP_BREAK_SYSTEM_PACKAGES=1 \
  -e EXPECTED_VERSION="$EXPECTED_VERSION" \
  -e E2E_SIMULATE_FAILURE="$SIMULATE_FAILURE" \
  -v "$PWD:/e2e" -w /e2e \
  "$IMAGE" \
  bash -c "pip install --quiet --user --no-warn-script-location -r requirements-e2e.txt \
    && python -m pytest . -v -p no:cacheprovider --base-url '$BASE_URL' \
         --junitxml=results/junit.xml --tracing retain-on-failure --output results/traces"
