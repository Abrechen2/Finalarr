#!/bin/sh
# Start backend (port 5790) and Vite dev server (proxying /api and /health) together.
set -e
cd "$(dirname "$0")/.."
(cd backend && . .venv/bin/activate && set -a && . ../.env && set +a && gunicorn -c gunicorn.conf.py 'finalarr.app:create_app()') &
trap 'kill $!' EXIT
cd frontend && npm run dev
