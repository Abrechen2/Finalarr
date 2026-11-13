#!/usr/bin/env bash
# End-to-end smoke test without Docker: demo Sonarr + Finalarr (gunicorn, built
# frontend, fresh data dir) + Playwright. Usage: e2e/run.sh  (from anywhere)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA="$(mktemp -d)"
APP_PORT=15791
SONARR_PORT=18990
PIDS=()
cleanup() { for p in "${PIDS[@]}"; do kill "$p" 2>/dev/null || true; done; rm -rf "$DATA"; }
trap cleanup EXIT

(cd "$ROOT/frontend" && npx vite build --logLevel error)
python3 "$ROOT/e2e/fake_sonarr.py" "$SONARR_PORT" & PIDS+=($!)

PYTHON="${PYTHON:-$ROOT/backend/.venv/bin/python}"
export FINALARR_API_KEY="e2e-api-key-0123456789abcdef"
export FINALARR_SECRET_KEY="$("$PYTHON" -c 'from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())')"
export FINALARR_DATA="$DATA" FINALARR_STATIC_DIR="$ROOT/frontend/dist" FINALARR_PORT="$APP_PORT"
export FINALARR_PUBLIC_URL="http://127.0.0.1:$APP_PORT"
(cd "$ROOT/backend" && "$PYTHON" -m gunicorn -c gunicorn.conf.py 'finalarr.app:create_app()') & PIDS+=($!)

for _ in $(seq 1 30); do curl -fsS "http://127.0.0.1:$APP_PORT/health" >/dev/null 2>&1 && break; sleep 1; done
cd "$ROOT/e2e"
FINALARR_URL="http://127.0.0.1:$APP_PORT" SONARR_URL="http://127.0.0.1:$SONARR_PORT" \
  FINALARR_API_KEY="$FINALARR_API_KEY" npx playwright test "$@"
