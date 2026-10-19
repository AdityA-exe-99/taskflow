#!/bin/bash
# Runs on the CI runner after the staging deploy. Copies the browser tests to the
# staging VM, runs them there against the new release, and copies the results back.
# A non-zero exit (any failed test) fails the staging job, so production is skipped.
# Usage: bash deploy/run-staging-e2e.sh <host> <ssh-key-file> <expected-version>
# Optional env: E2E_SIMULATE_FAILURE=true (presentation demo)
# Owner: Abhinav (Test/Staging)
set -euo pipefail
HOST="$1"
KEY="$2"
VERSION="$3"
SSH="ssh -i $KEY -o StrictHostKeyChecking=accept-new deploy@$HOST"
REMOTE=/opt/aerodeploy/e2e

# fresh copy of the tests each run (tar keeps it to one connection and works with any scp version)
$SSH "rm -rf $REMOTE && mkdir -p $REMOTE"
tar -C tests/e2e --exclude=results --exclude=__pycache__ -cf - . | $SSH "tar -C $REMOTE -xf -"

set +e
$SSH "E2E_SIMULATE_FAILURE=${E2E_SIMULATE_FAILURE:-false} bash $REMOTE/run.sh $VERSION"
status=$?
set -e

# bring back the JUnit report and any failure traces for the pipeline artifact
mkdir -p test-results/e2e
$SSH "tar -C $REMOTE/results -cf - ." | tar -C test-results/e2e -xf - || true

if [ "$status" -ne 0 ]; then
  echo "Browser tests FAILED on staging: production will not be deployed"
fi
exit $status
