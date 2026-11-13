# Changelog

All notable changes to Finalarr are documented here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versions follow SemVer.

## [0.3.0] – not released yet

The first version that does the whole job: it watches Sonarr, knows how many episodes a
season will have, and tells you once — when new episodes are on disk, when the finale has
landed and when a season is complete.

### Added
- **Sonarr**: connect one or more instances (connection test, encrypted API key), webhook
  URL to paste into Sonarr (optional Basic auth, IP allowlist), sync every 30 minutes and
  right after each webhook. The webhook only triggers a sync; nothing in its body is trusted.
- **Series**: follow series one by one or all monitored ones at once; search and filter;
  per series you decide whether specials count and whether unmonitored episodes are ignored.
- **Season logic**: expected episode count from Sonarr, cross-checked with AniList for anime
  (split cours included). When the two disagree the season shows "Folgenzahl unklar" and
  waits; one click takes either number. Seasons Sonarr does not list yet are announced from
  AniList. "Jetzt prüfen" shows what Finalarr would report right now without sending anything.
- **Reports**: "verfügbar" (as episode ranges, one message per batch), "Finale", "Teil
  komplett" for split cours, "Staffel komplett" and "angekündigt" — each at most once, never
  for what was already on disk when you started following.
- **Channels**: Telegram, Discord, Pushover, generic webhook or any Apprise URL; message
  language, event filter and quiet hours per channel; test message; failed sends are
  retried twice and then shown with the reason; resend from the event log.
- **UI** (German, English switchable): overview, series, events, settings, setup wizard,
  dark and light theme.
- Runs as one Docker container (non-root, PUID/PGID, healthcheck, data in `/config`);
  refuses to start without `FINALARR_API_KEY` and `FINALARR_SECRET_KEY`.
