<p align="center"><img src="assets/icon-512.png" width="96" alt="Finalarr"></p>

# Finalarr

Season-finale and season-complete notifier for Sonarr. Finalarr tells you when a
followed series or anime has new episodes in your library, when its season finale
has landed, and when a season is complete — once, on Telegram (more channels later).

**Status:** 0.3.0, feature-complete MVP, not released yet. Expect changes.

## What it does

- Watches one or more Sonarr v4 instances (webhook + periodic sync).
- Keeps an expected episode count per season — from Sonarr, cross-checked with AniList for
  anime, split cours included — and tells you when the two disagree instead of guessing.
- Reports, each exactly once: new episodes on disk (as ranges), the season finale, a
  completed split-cour part, a complete season, and seasons announced before Sonarr knows
  them.
- Sends to Telegram, Discord, Pushover, a webhook or any [Apprise](https://github.com/caronc/apprise)
  URL, in German or English, with quiet hours.
- Small web UI in English and German (follows your browser), dark and light theme, one
  Docker container, SQLite. Design notes: [docs/DESIGN.md](docs/DESIGN.md).

## Is it for you?

Yes, if you use Sonarr and want to know when a season is *done* — especially for anime with
split cours or Netflix-style batch releases. No, if you want a calendar, a downloader or
movie support (Radarr is not supported).

## Why

Sonarr has no "season complete" event: imports fire per batch and know nothing about
how many episodes a season will have. Finalarr keeps an expected-episode model per
season (Sonarr, plus AniList for anime), a state machine with memory, and idempotent
notifications.

## Quick start

See [docs/DEPLOY.md](docs/DEPLOY.md). In short: set `FINALARR_API_KEY` and
`FINALARR_SECRET_KEY`, run the container on port 5790, open it, follow the setup.

## Development

```sh
cd backend && uv venv -p 3.12 .venv && . .venv/bin/activate && uv pip install -e '.[dev]' && pytest
cd frontend && npm ci && npm test
docker compose up --build   # http://localhost:5790
e2e/run.sh                  # end-to-end smoke test with a demo Sonarr
```

## Privacy

Finalarr talks to your Sonarr, the notification channels you configure, and public
metadata sources to learn about seasons and announcements: AniList and Fribb's
anime-lists (GitHub), MyAnimeList via Jikan, TVmaze, LiveChart.me and Anime News Network,
plus TMDB and Trakt only if you add their keys. It sends them TVDB/AniList ids or plain
search terms — never your Sonarr address, keys or library contents. No telemetry.

## Licence

GPL-3.0 — see [LICENSE](LICENSE).

---

A project by [`<abrechen2 />`](https://www.abrechen2.de/en/).
