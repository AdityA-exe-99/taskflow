#!/bin/bash
# Run the existing suites on staging against an isolated, temporary PostgreSQL DB.
set -euo pipefail
HOST="$1"
KEY="$2"
VERSION="$3"
RUN_ID="${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}"
[[ "$VERSION" =~ ^[a-f0-9]{40}$ ]] || { echo "Invalid commit SHA"; exit 1; }
[[ "$RUN_ID" =~ ^[a-zA-Z0-9-]+$ ]] || { echo "Invalid run ID"; exit 1; }
REMOTE="/opt/aerodeploy/unit-integration-$RUN_ID"
SSH=(ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "deploy@$HOST")
REPORTS="test-results/staging-unit-integration"
mkdir -p "$REPORTS"
"${SSH[@]}" "mkdir -p '$REMOTE'"
tar -cf - Dockerfile.test docker-compose.test.yml requirements-test-lock.txt tests/run_tests.py tests/unit tests/integration \
  | "${SSH[@]}" "tar -C '$REMOTE' -xf -"
set +e
"${SSH[@]}" bash -s -- "$REMOTE" "$VERSION" "$RUN_ID" <<'REMOTE_SCRIPT' 2>&1 | tee "$REPORTS/execution.log"
set -euo pipefail
cd "$1"
export TASKFLOW_TEST_BASE="ghcr.io/aditya-exe-99/taskflow:$2"
export TASKFLOW_TEST_IMAGE="taskflow-staging-tests:$3"
export TASKFLOW_TEST_REPORTS="$PWD/results"
PROJECT="staging-tests-$3"
cleanup() {
  result=$?
  trap - EXIT
  docker compose -p "$PROJECT" -f docker-compose.test.yml down -v || true
  # one test image per run would slowly fill the staging disk
  docker image rm -f "$TASKFLOW_TEST_IMAGE" >/dev/null 2>&1 || true
  exit "$result"
}
trap cleanup EXIT
mkdir -p results
chmod 777 results
# The staging deployment has already pulled this exact release image.
docker image inspect "$TASKFLOW_TEST_BASE" --format '{{.Id}}'
printf 'Test server: %s\nRelease: %s\n' "$(hostname)" "$TASKFLOW_TEST_BASE"
docker compose -p "$PROJECT" -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from tests
REMOTE_SCRIPT
status=${PIPESTATUS[0]}
set -e
# Fetch evidence even when a test failed; missing reports must not count as success.
if ! "${SSH[@]}" "tar -C '$REMOTE/results' -cf - ." | tar -C "$REPORTS" -xf -; then
  echo "Unable to retrieve staging test reports"
  exit 1
fi
# Remove this run's working folder from staging. The reports were written by the
# container's non-root user, so they are removed with the release image itself.
"${SSH[@]}" "docker run --rm --user root --entrypoint rm -v '$REMOTE:/r' 'ghcr.io/aditya-exe-99/taskflow:$VERSION' -rf /r/results && rm -rf '$REMOTE'" \
  || echo "Warning: could not remove $REMOTE on staging"
if [ "$status" -ne 0 ]; then
  echo "Unit/integration tests failed on staging; production is blocked"
  exit "$status"
fi
test -s "$REPORTS/junit.xml"
test -s "$REPORTS/coverage.xml"
echo "Unit and integration suites passed on Test/Staging"
