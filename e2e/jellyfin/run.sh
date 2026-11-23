#!/usr/bin/env bash
# Acceptance test against a real Jellyfin in a throwaway container: Finalarr's client and
# media sync (users, TVDB matching, paging, specials, unwatching, auto-follow, tracker,
# outage). Needs Docker and the backend venv. Usage: e2e/jellyfin/run.sh [image tag]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
TAG="${1:-latest}"
WORK="$(mktemp -d)"
trap 'docker rm -f finalarr-jf >/dev/null 2>&1 || true; rm -rf "$WORK"' EXIT

docker rm -f finalarr-jf >/dev/null 2>&1 || true
docker run -d --name finalarr-jf -p 127.0.0.1:18096:8096 \
  --tmpfs /config --tmpfs /cache --tmpfs /media "jellyfin/jellyfin:$TAG" >/dev/null
# One-second clips: two shows with TVDB ids in the folder name, one without.
docker exec finalarr-jf sh -c '
F=/usr/lib/jellyfin-ffmpeg/ffmpeg
$F -loglevel error -f lavfi -i color=black:s=64x36:d=1 -c:v libx264 /tmp/e.mkv
mk() { d="/media/shows/$1/Season $(printf %02d $2)"; mkdir -p "$d"
  for e in $(seq 1 $3); do cp /tmp/e.mkv "$d/$4 - S$(printf %02d $2)E$(printf %02d $e).mkv"; done; }
mk "Severance (2022) [tvdbid-371980]" 1 9 Severance
mk "Severance (2022) [tvdbid-371980]" 2 4 Severance
mk "Frieren (2023) [tvdbid-424536]" 1 6 Frieren
mk "Frieren (2023) [tvdbid-424536]" 0 1 Frieren
mk "Unknown Show" 1 2 "Unknown Show"'
for _ in $(seq 60); do curl -fsS http://127.0.0.1:18096/System/Info/Public >/dev/null 2>&1 && break; sleep 2; done

PYTHON="${PYTHON:-$ROOT/backend/.venv/bin/python}"
cd "$ROOT/backend"
"$PYTHON" "$HERE/setup.py" "$WORK/ids.json"
"$PYTHON" "$HERE/flow.py" "$WORK/ids.json"
