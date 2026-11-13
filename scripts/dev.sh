#!/bin/sh
# Start backend (port 5790) and Vite dev server (proxying /api and /health) together.
set -e
cd "$(dirname "$0")/.."
(cd backend && . .venv/bin/activate && flask --app 'finalarr.app:create_app()' run --port 5790) &
trap 'kill $!' EXIT
cd frontend && npm run dev
