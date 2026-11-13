# Finalarr

Season-finale and season-complete notifier for Sonarr. Finalarr tells you when a
followed series or anime has new episodes in your library, when its season finale
has landed, and when a season is complete — once, on Telegram (more channels later).

**Status:** early development (0.0.x). Not usable yet.

## Why

Sonarr has no "season complete" event: imports fire per batch and know nothing about
how many episodes a season will have. Finalarr keeps an expected-episode model per
season (Sonarr, plus AniList for anime), a state machine with memory, and idempotent
notifications.

## Quick start (development)

```sh
cd backend && uv venv -p 3.12 .venv && . .venv/bin/activate && uv pip install -e '.[dev]' && pytest
cd frontend && npm ci && npm test
docker compose up --build   # http://localhost:5790
```

## Privacy

Finalarr talks only to your Sonarr, AniList (title lookups) and the notification
channels you configure. No telemetry.

## Licence

GPL-3.0 — see [LICENSE](LICENSE).

---

A project by [`<abrechen2 />`](https://www.abrechen2.de/en/) — `// Self-built. Self-hosted.`
