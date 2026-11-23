#!/usr/bin/env bash
# Starts an image with throwaway keys and waits until /health answers (release workflow).
# Usage: docker/start-test.sh IMAGE [--platform linux/arm64]
set -euo pipefail
image="$1"; shift
docker rm -f smoke >/dev/null 2>&1 || true
docker run -d --name smoke "$@" -p 5790:5790 \
  -e FINALARR_API_KEY="$(openssl rand -hex 32)" \
  -e FINALARR_SECRET_KEY="$(openssl rand -base64 32 | tr '+/' '-_')" "$image" >/dev/null
# arm64 runs under emulation and needs longer to start.
for _ in $(seq 1 90); do
  if curl -fsS http://127.0.0.1:5790/health; then docker rm -f smoke >/dev/null; exit 0; fi
  sleep 2
done
docker logs smoke
exit 1
