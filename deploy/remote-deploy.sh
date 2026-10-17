#!/bin/bash
# Runs on the CI runner. Copies the deploy files to a server and deploys an image tag there.
# Usage: bash remote-deploy.sh <host> <ssh-key-file> <image-tag>
# Needs env vars: DB_PW, APP_SECRET, GHCR_TOKEN, GHCR_USER
set -euo pipefail
HOST="$1"
KEY="$2"
TAG="$3"
SSH_OPTS="-i $KEY -o StrictHostKeyChecking=accept-new"

# always log out of GHCR on the server, even if the deploy fails
trap 'ssh $SSH_OPTS deploy@$HOST "docker logout ghcr.io" >/dev/null 2>&1 || true' EXIT

scp $SSH_OPTS deploy/docker-compose.yml deploy/deploy.sh deploy@$HOST:/opt/aerodeploy/

# secrets go over stdin, so they never appear in logs or on the command line
printf 'IMAGE_TAG=%s\nPOSTGRES_PASSWORD=%s\nSECRET_KEY=%s\n' "$TAG" "$DB_PW" "$APP_SECRET" \
  | ssh $SSH_OPTS deploy@$HOST 'umask 077; cat > /opt/aerodeploy/.env.new'

echo "$GHCR_TOKEN" | ssh $SSH_OPTS deploy@$HOST "docker login ghcr.io -u $GHCR_USER --password-stdin" >/dev/null

ssh $SSH_OPTS deploy@$HOST "bash /opt/aerodeploy/deploy.sh $TAG"