#!/bin/bash
# Runs on the staging/production VM. The pipeline calls it over SSH.
# Usage: bash deploy.sh <image-tag>
set -euo pipefail
cd /opt/aerodeploy
NEW_TAG="$1"
PROJECT=aerodeploy-taskflow

# remember what is running now so we can roll back
PREV_TAG=$(grep -s '^IMAGE_TAG=' .env | cut -d= -f2 || true)
echo "Current version: ${PREV_TAG:-none}"
echo "New version:     $NEW_TAG"

# back up the database before changing anything (skipped on the very first deploy)
if docker compose -p $PROJECT ps --status running -q db 2>/dev/null | grep -q .; then
  mkdir -p backups
  docker compose -p $PROJECT exec -T db pg_dump -U taskflow taskflow > "backups/pre-deploy-$(date +%F-%H%M%S).sql"
  ls -t backups/*.sql | tail -n +8 | xargs -r rm
  echo "Database backed up"
fi

# the pipeline sends the secrets as .env.new; it becomes the live .env
mv .env.new .env
chmod 600 .env

# network shared with the monitoring stack
docker network create aerodeploy-taskflow_default >/dev/null 2>&1 || true

docker compose -p $PROJECT pull web
docker compose -p $PROJECT up -d

# health check: /health must return 200 within 60 seconds
for i in $(seq 1 12); do
  if curl -fsS http://127.0.0.1:8000/health; then
    echo
    echo "Deploy OK: $NEW_TAG"
    exit 0
  fi
  sleep 5
done

echo "Health check failed for $NEW_TAG"
docker compose -p $PROJECT logs --tail 50 web

# roll back to the previous image if there was one
if [ -n "$PREV_TAG" ] && [ "$PREV_TAG" != "$NEW_TAG" ]; then
  echo "Rolling back to $PREV_TAG"
  sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=$PREV_TAG/" .env
  docker compose -p $PROJECT up -d
fi
exit 1