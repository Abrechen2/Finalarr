# Changelog

All notable changes to Finalarr are documented here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versions follow SemVer.

## [0.5.0] – 2026-11-25

### Added
- **Watched tab**: for everyone or one person, episodes and hours watched, this week and
  month, a chart of episodes per week, and every started series with what is still
  missing: behind, untouched for over 30 days, caught up, finished, or not followed. Each
  row names the next unwatched episode; filters and sorting by last watched, most
  unwatched or title.
- **Episode counts for live action** from TVmaze, TMDB and Trakt (Forgejo #22): when they
  know more episodes than Sonarr lists, the season waits for them instead of being
  reported complete, as AniList already did for anime.
- Before a new version migrates the database, it is copied to
  `backups/finalarr-before-<revision>-<time>.db` (the newest five are kept).
- The system tab shows when each background job last ran, the error of a failed run, and
  flags a job without a good run for two intervals.
- A page that crashes shows a message instead of a blank app; unknown addresses get a
  not-found page.
- `e2e/jellyfin/run.sh`: acceptance test against a real Jellyfin in a throwaway container.

### Fixed
- **Jellyfin 12 connections failed** with "rejected the token": it accepts the key only in
  the `Authorization` header now. Older Jellyfin versions take it as well; Emby is
  unchanged.
- **Database upgrades could delete rows**: rebuilding a table during a migration cascaded
  into its children (the 0.4.0 upgrade re-created all seasons and episodes, and unlinked
  some events from their season). Foreign keys are off while migrations run and checked
  afterwards; a test upgrades a populated first-version database to the current one.
- A series missing from a single Sonarr answer was deleted with its follow state,
  overrides and watch history. It now goes only when two full syncs in a row miss it, and
  an empty list removes nothing.
- A Sonarr key or media-server token the current `FINALARR_SECRET_KEY` cannot decrypt is
  shown as that connection's error instead of stopping the sync.
- Selecting a second media-server user while a sync ran left them at zero episodes for up
  to 30 minutes; the sync now runs again right away. The same race could delay a Sonarr
  webhook by a few seconds, and made a scheduler test fail now and then (Forgejo #26).
- Failed actions on Sonarr instances and media servers (disable, sync, rotate, delete)
  are shown. Removing a media server, which deletes its watch history, asks first.
- The page language is set from the first render (screen readers), not only after a
  language switch.

### Changed
- The interface uses the full window width: series in two columns from 1400 px, the
  series page puts news beside the details.
- On phones, About moved from the bottom bar into the header to make room for Watched.
- Python libraries are pinned with hashes, so a release candidate and its final build
  ship the same versions; the release workflow also start-tests the pushed image digest.
- Docs: restore checklist, the delivery guarantee (at most a rare duplicate after a crash
  between sending and recording), English menu names.

## [0.4.1] – 2026-11-23

### Fixed
- **Memory:** the container was killed for exceeding its memory limit every one or two
  days. Python freed its objects, but glibc kept the freed memory and the many
  short-lived objects of each sync fragmented its heap; the weekly refresh of Fribb's
  anime list then added a 79 MB peak on top. Background jobs now hand free memory back
  to the system, the image limits glibc to two arenas, and the Fribb list is parsed once
  and stored with bulk inserts (peak 32 MB). Measured on a 700-series library: flat at
  ~124 MB instead of growing past 250 MB. A job that grows the process by 30 MB or more
  is now logged. The Compose example allows 384 MB.
- **Quiet hours** ended an hour late in winter (two in summer): the end of the window was
  stored in local time, and SQLite drops the offset, so it was read back as UTC.
- gunicorn 27 logged "Permission denied" on every start for its control socket, which
  Finalarr does not use; it is switched off.

### Changed
- Frontend builds with Vite 8 (Rolldown) and @vitejs/plugin-react 6; libraries ship as a
  separate chunk that stays cached across Finalarr updates.
- Dependencies: Apprise 2, icalendar 7, gunicorn 27, current ESLint plugins.

## [0.4.0] – 2026-11-15

The first release. Finalarr learns what you actually watch, and it includes everything
listed under 0.3.0 below, which was never released on its own.

### Added
- **Emby, Jellyfin and Plex**: connect one or more media servers (connection test, token
  stored encrypted) and pick whose viewing counts — family members and Plex Home managed
  users included. Finalarr reads which episodes they watched every 30 minutes and matches
  the series to Sonarr by TVDB id.
- **Follow automatically**: a series someone watched at least 2 episodes of within 30 days
  is followed on its own (both numbers adjustable, can be switched off). Each series has a
  follow mode: automatic, always (followed by hand) or never; what you followed before
  stays followed. Finalarr never unfollows on its own.
- **Watched state in the UI**: who watched how much of a series and when, which episodes
  in the grid are watched and by whom, how many episodes on disk are still unwatched and
  which one is next; list filters for started, behind and caught-up series and by follow
  mode; a "Weiterschauen" list on the dashboard. Without a media server none of this shows.

### Security
- Changing the address of a Sonarr instance or media server now needs the key again, so
  a stored key can never be sent to a new host.

### Privacy
- Stored per selected user: which episodes were watched and on which day. No viewing
  history, playback positions, devices or IP addresses; deselecting a user deletes their
  data.

## [0.3.0] – not released separately, part of 0.4.0

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
- **UI** in English and German (follows the browser, switchable): overview, series, events,
  settings, setup wizard, dark and light theme, with Finalarr's own look — a tally mark,
  dusk rose for what is running and gold for what is finished (docs/DESIGN.md).
- **Sequels announced early**: when AniList lists a sequel of a season you follow that has
  not started yet (e.g. a 2027 continuation), Finalarr reports it once as "Fortsetzung
  angekündigt", before TheTVDB or Sonarr know the season. Anime typed "Standard" in Sonarr
  now get AniList data too.
- **News on every series page**: Finalarr's own announcements and matched headlines,
  then the latest web headlines about the series — only season and episode news that name
  the series in the headline (no merchandise, films, manga, games, listicles or reviews) (Google News, in your UI language,
  cached for 6 hours; can be switched off in the rules).
- **Calendar**: a month view of what you are waiting for and a subscribable iCal feed
  (Google, Apple, Outlook). Choose season finales only, premieres and finales, or every
  episode; hide what is already on disk; show announced start dates; switch single series
  off. The feed address is secret, can be renewed and switched off.
- **More sources**: TVmaze (no key) and, with a free key each, TMDB and Trakt announce
  renewed TV seasons early; MyAnimeList (Jikan) backs up AniList for anime sequels;
  LiveChart.me and Anime News Network headlines that name a followed series arrive as
  "In den News" hints with a link. One message per season or sequel, whatever the source.
- **What you are waiting for**, on every series page in one sentence ("Staffel 3 ist
  angekündigt, der Termin ist noch offen", "2 ausgestrahlte Folgen fehlen noch", …), plus
  the next episode with a countdown and its exact time (Sonarr, AniList or TVmaze), the
  channel, "where to watch" links (AniList; per country from TMDB/JustWatch with a key), a
  trailer that loads from YouTube only after a click, and Sonarr's overview, network,
  runtime, genres and fanart. The dashboard counts down to the next episode too.
- **Postponed episodes**: when an upcoming episode's air date moves back by a day or more
  (or disappears), Finalarr reports "verschoben" with the old and new date and marks the
  episode in the grid and the calendar.
- **Typed news**: headlines are sorted into renewal, announcement, cancellation, delay,
  date and trailer, with the sentence that carries the news; Anime2You (DE) and Crunchyroll
  News (EN) join the news feeds.
- **English dub dates** from AnimeSchedule.net with an optional app token
  (`FINALARR_ANIMESCHEDULE_TOKEN`).
- `FINALARR_AUTH=local`: no login from your home network; the API key is still needed from
  anywhere else.
- **Data sources page** (*Einstellungen → Datenquellen*): every outside service Finalarr
  asks, what for and under which terms, each with an on/off switch. The About page credits
  the sources (TMDB logo and notice, TVmaze under CC BY-SA, JustWatch), and the series page
  links back to the source of each piece of data.
- **Setup shows that it works**: the first sync with Sonarr and the first webhook call
  (Sonarr's "Test" button) are confirmed live.
- **Backups while running**: `docker exec finalarr python -m finalarr.backup`.
- **Open source** on GitHub: CI, release images on GHCR (amd64; arm64 too for final
  releases; published only after CI and a start test, with SBOM, provenance and a cosign
  signature), Unraid Community Applications template, issue templates, private security
  reporting, licence notices in the image (`/licenses/INDEX.txt`).
- Runs as one Docker container (non-root, PUID/PGID, healthcheck, data in `/config`);
  refuses to start without `FINALARR_API_KEY` and `FINALARR_SECRET_KEY`.

### Security
- `FINALARR_AUTH=local` no longer trusts forwarded requests unless
  `FINALARR_TRUSTED_PROXIES` is set; behind an unconfigured proxy every visitor looked local.
- Logs strip bot tokens, webhook secrets, passwords and token parameters from HTTP(S)
  URLs that Apprise prints.

