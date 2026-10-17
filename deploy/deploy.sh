#!/bin/bash
# Runs on the staging/production VM. The pipeline calls it over SSH.
# Usage: bash deploy.sh <image-tag>
set -euo pipefail
cd /opt/aerodeploy
NEW_TAG="$1"
PROJECT=aerodeploy-taskflow

# /health must return 200 within 60 seconds
health_ok() {
  for i in $(seq 1 12); do
    if curl -fs http://127.0.0.1:8000/health; then
      echo
      return 0
    fi
    sleep 5
  done
  return 1
}

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

# keep the current image + settings for rollback, then switch to the new ones
if [ -f .env ]; then cp .env .env.prev; fi
mv .env.new .env
chmod 600 .env

# network shared with the monitoring stack
docker network create aerodeploy-taskflow_default >/dev/null 2>&1 || true

docker compose -p $PROJECT pull web
docker compose -p $PROJECT up -d

if health_ok; then
  echo "Deploy OK: $NEW_TAG"
  exit 0
fi

echo "Health check failed for $NEW_TAG"
docker compose -p $PROJECT logs --tail 30 web

# roll back to the previous image and settings
if [ -f .env.prev ]; then
  echo "Rolling back to ${PREV_TAG}"
  mv .env.prev .env
  docker compose -p $PROJECT up -d
  if health_ok; then
    echo "Rollback OK: running ${PREV_TAG} again"
  else
    echo "Rollback health check also failed"
  fi
fi
exit 1