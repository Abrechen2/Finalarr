#!/usr/bin/env bash
# Build the amd64 image here, ship it over SSH and restart Finalarr on the target.
#
#   DEPLOY_HOST=root@unraid scripts/deploy.sh [--rc N] [--yes] [--dry-run]
#
# Env: DEPLOY_HOST (required, ssh target), DEPLOY_DIR (default
# /mnt/user/appdata/finalarr), DEPLOY_PORT (default 5790).
# Without --yes it shows the plan and asks once; nothing restarts unconfirmed.
# RC images are amd64 only; multi-arch is only built for a final release.
set -euo pipefail
cd "$(dirname "$0")/.."

RC="" YES=0 DRY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --rc) RC="$2"; shift 2 ;;
    --yes) YES=1; shift ;;
    --dry-run) DRY=1; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

: "${DEPLOY_HOST:?set DEPLOY_HOST, e.g. root@unraid}"
DIR="${DEPLOY_DIR:-/mnt/user/appdata/finalarr}"
PORT="${DEPLOY_PORT:-5790}"
VERSION="$(cat backend/VERSION)${RC:+-rc.$RC}"
IMAGE="finalarr:${VERSION}"

cat <<PLAN
Deploy plan
  image    ${IMAGE} (linux/amd64)
  target   ${DEPLOY_HOST}:${DIR}
  steps    build → docker save | ssh docker load → copy compose files →
           docker compose up -d → wait for /health on port ${PORT}
PLAN
[ "$DRY" = 1 ] && { echo "(dry run, nothing done)"; exit 0; }
if [ "$YES" != 1 ]; then
  read -r -p "Deploy now and restart Finalarr on ${DEPLOY_HOST}? [y/N] " answer
  [ "$answer" = "y" ] || { echo "aborted"; exit 1; }
fi

docker build --platform linux/amd64 --build-arg VERSION="$VERSION" -t "$IMAGE" .
docker save "$IMAGE" | ssh "$DEPLOY_HOST" docker load
ssh "$DEPLOY_HOST" "mkdir -p '$DIR/compose'"
scp -q docker-compose.yml docker-compose.unraid.yml "$DEPLOY_HOST:$DIR/compose/"
ssh "$DEPLOY_HOST" "cd '$DIR/compose' && FINALARR_IMAGE='$IMAGE' docker compose \
  -f docker-compose.yml -f docker-compose.unraid.yml up -d --no-build"

for _ in $(seq 1 30); do
  if ssh "$DEPLOY_HOST" "curl -fsS http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
    echo "Finalarr ${VERSION} is healthy."
    exit 0
  fi
  sleep 2
done
echo "Finalarr did not become healthy; check: ssh $DEPLOY_HOST docker logs finalarr" >&2
exit 1
