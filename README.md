<p align="center"><img src="assets/icon-512.png" width="96" alt="Finalarr"></p>

# Finalarr

[![CI](https://github.com/Abrechen2/Finalarr/actions/workflows/ci.yml/badge.svg)](https://github.com/Abrechen2/Finalarr/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Abrechen2/Finalarr?include_prereleases&label=release)](https://github.com/Abrechen2/Finalarr/releases)
[![Image](https://img.shields.io/badge/image-ghcr.io-2496ed)](https://github.com/Abrechen2/Finalarr/pkgs/container/finalarr)
[![Licence](https://img.shields.io/badge/licence-GPL--3.0-blue)](LICENSE)

**Season-finale and season-complete notifier for Sonarr.** Finalarr tells you — once —
when a series or anime you follow has new episodes on disk, when its season finale has
landed and when the season is complete. It also tells you what you are still waiting for:
renewals, announced sequels, postponed episodes and the next air date.

> **Status:** 0.3 release candidates. It runs daily against a real library, but expect
> changes until 1.0.

## What it does

- **Knows how long a season is.** Expected episode count from Sonarr, cross-checked with
  AniList for anime (split cours included). When the two disagree it says so instead of
  guessing; one click picks either number.
- **Reports each thing exactly once:** new episodes on disk (as ranges, one message per
  batch), the season finale, a finished split-cour part, a complete season, a season or
  sequel announced before Sonarr knows it, and an episode whose air date was postponed.
  Nothing is reported for what was already on disk when you started following.
- **Shows what you are waiting for** on every series page: one sentence ("Season 3 is
  announced; the date is still open"), the next episode with a countdown, where to watch
  it, the trailer (loaded only on click) and season/episode news without merchandise.
- **Follows what you watch**: connect Emby, Jellyfin or Plex, pick whose viewing counts, and
  Finalarr follows the series you actually watch — and shows who watched which episode and
  what is still unwatched.
- **Calendar** in the app and as a subscribable iCal feed — finales only, premieres and
  finales, or every episode.
- **Channels:** Telegram, Discord, Pushover, a webhook or any
  [Apprise](https://github.com/caronc/apprise) URL; German or English messages, event
  filter and quiet hours per channel.
- One Docker container, SQLite, web UI in English and German, dark and light theme.

**Not for you** if you want a downloader, movie support (Radarr) or Sonarr v3.

## Install

Finalarr needs two keys. Generate them once and keep them:

```sh
openssl rand -hex 32                          # FINALARR_API_KEY (also your login)
openssl rand -base64 32 | tr '+/' '-_'        # FINALARR_SECRET_KEY (encrypts stored secrets)
```

### Docker Compose

```yaml
services:
  finalarr:
    image: ghcr.io/abrechen2/finalarr:latest   # or a release tag such as 0.3.0
    container_name: finalarr
    restart: unless-stopped
    ports:
      - "5790:5790"
    environment:
      - FINALARR_API_KEY=change-me
      - FINALARR_SECRET_KEY=change-me
      - PUID=1000
      - PGID=1000
      - TZ=Europe/Berlin
      # - FINALARR_AUTH=local   # no login from your home network
    volumes:
      - ./finalarr:/config
    stop_grace_period: 90s
```

```sh
docker compose up -d   # then open http://<host>:5790 and follow the setup
```

Until 0.3.0 is final, only release candidates exist: use `ghcr.io/abrechen2/finalarr:rc-latest`.

### Unraid

Search for **Finalarr** in Community Applications, or use the template in
[`unraid/my-finalarr.xml`](unraid/my-finalarr.xml).

Keep it inside your home network: don't forward port 5790; for remote access use a VPN or
a reverse proxy with HTTPS (see [docs/DEPLOY.md](docs/DEPLOY.md)).

### Setup

The setup page walks you through it: add your Sonarr (URL and API key), paste the
webhook URL Finalarr shows into *Sonarr → Settings → Connect → Webhook*, choose the series
to follow and add a notification channel. All other options, optional keys (TMDB, Trakt,
AnimeSchedule.net), backups, updates and reverse-proxy notes: [docs/DEPLOY.md](docs/DEPLOY.md).

## Privacy

Finalarr talks to your Sonarr, your media servers (Emby, Jellyfin, Plex) if you connect
them, the notification channels you configure, and public metadata sources: AniList and Fribb's anime-lists (GitHub), MyAnimeList via Jikan, TVmaze,
the news feeds of LiveChart.me, Anime News Network, Anime2You and Crunchyroll, Google News
(the series title, for the news box; can be switched off), plus TMDB, Trakt and
AnimeSchedule.net only if you add their keys. Every source can be switched off under
*Settings → Data sources*, which also lists each one's terms. A trailer is loaded from YouTube
(youtube-nocookie.com) only when you click it. It sends TVDB/AniList ids or plain search
terms — never your Sonarr address, keys or library contents. No telemetry.

## Development

```sh
cd backend && python3.12 -m venv .venv && . .venv/bin/activate && pip install -e '.[dev]' && pytest
cd frontend && npm ci && npm test
docker compose up --build   # http://localhost:5790
e2e/run.sh                  # end-to-end test with a demo Sonarr
```

See [CONTRIBUTING.md](CONTRIBUTING.md). Design notes: [docs/DESIGN.md](docs/DESIGN.md).
Security issues: [SECURITY.md](SECURITY.md).

## Licence

GPL-3.0 — see [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
This product uses the TMDB API but is not endorsed or certified by TMDB.

---

A project by [`<abrechen2 />`](https://www.abrechen2.de/en/).
