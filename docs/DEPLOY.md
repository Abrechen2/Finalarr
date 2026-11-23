# Deploying Finalarr

> **Keep Finalarr inside your home network.** Do not forward port 5790 to the internet.
> For access from outside use a VPN, or a reverse proxy with HTTPS (see *Remote access*
> below). With `FINALARR_AUTH=local`, anyone on your network can use Finalarr without
> logging in.

## Requirements

- Docker, amd64 or arm64 (release candidates are amd64 only). Image:
  `ghcr.io/abrechen2/finalarr` (`latest`, a version such as `0.3.0`, or `rc-latest`).
- Sonarr v4 reachable from the container.
- Two secrets in the environment (Finalarr refuses to start without them):
  - `FINALARR_API_KEY` — at least 20 characters, e.g. `openssl rand -hex 32`. It is also
    the UI login.
  - `FINALARR_SECRET_KEY` — a Fernet key: `openssl rand -base64 32 | tr '+/' '-_'`.
    It encrypts stored Sonarr keys and channel URLs; changing it makes them unreadable.

Optional: `FINALARR_AUTH=local` (no login from home networks, like Sonarr's "disabled for
local addresses"; behind a reverse proxy also set `FINALARR_TRUSTED_PROXIES`, or every
request looks local), `FINALARR_PUBLIC_URL` (adds "Finalarr" links to messages),
`FINALARR_TRUSTED_PROXIES` (number of reverse proxies in front),
`FINALARR_WEBHOOK_ALLOW` (IPs/CIDRs allowed to call the webhook), `PUID`/`PGID`, `TZ`.
See `.env.example`.

## Docker Compose

The README has a ready-to-use compose file with the published image. To build from a
checkout instead:

```sh
cp .env.example .env   # fill in the two keys
docker compose up -d --build
```

Data lives in `/config` (SQLite database, log, scheduler lock).

## Updates and backups

Pull the new image and recreate the container (`docker compose pull && docker compose up
-d`). When a new version changes the database, Finalarr copies it first to
`/config/backups/finalarr-before-<revision>-<time>.db` (the newest five are kept) and then
migrates it. Migrations are not reversible: to go back to an older version, restore that
copy (below) and run the older image.

Backup while Finalarr runs (a plain `cp` of `finalarr.db` can catch it mid-write):

```sh
docker exec finalarr python -m finalarr.backup        # → /config/backups/finalarr-<time>.db
```

Or stop the container and copy the whole `/config` folder. Keep both keys with the
backup: without the same `FINALARR_SECRET_KEY` a restored database cannot decrypt the
stored Sonarr keys and channel URLs. To restore, stop the container, put the backup in
place as `/config/finalarr.db` (delete `finalarr.db-wal` and `finalarr.db-shm` next to
it) and start again with the same keys. Then check:

1. `/health` answers and the log shows no migration error.
2. *Settings → Sonarr* shows no "cannot be decrypted" error (a wrong `FINALARR_SECRET_KEY`
   shows up here first) and *Sync now* works.
3. *Events* lists the old notifications, and a channel's *Test* message arrives.

Restoring a backup from an older version is fine: it is migrated on start. A backup from
a newer version does not run on an older image.

## Remote access and HTTPS

Finalarr speaks plain HTTP. For access from outside your network put it behind a reverse
proxy with HTTPS and set:

- `FINALARR_COOKIE_SECURE=true` — the login cookie is only sent over HTTPS;
- `FINALARR_TRUSTED_PROXIES=1` (number of proxies) — so Finalarr sees the real client
  address for rate limits and `FINALARR_AUTH=local`. With `local` and no trusted proxy,
  forwarded requests always need the API key;
- `FINALARR_PUBLIC_URL` — the address you open, for links in messages.

Sonarr URL and channel URLs are requests Finalarr makes on your behalf; only people with
the API key can set them, so keep the key private.

## Unraid

Install Finalarr from Community Applications (template: `unraid/my-finalarr.xml`). With
Compose: `docker-compose.unraid.yml` is an overlay with `PUID=99`, `PGID=100`, the appdata
path and an env file. For your own builds, `DEPLOY_HOST=root@unraid scripts/deploy.sh
[--rc N]` builds amd64, loads it over SSH, restarts the container and waits for `/health`;
it asks before restarting.

## Media servers (Emby, Jellyfin, Plex)

*Settings → Media servers*: add the server address and a key, test, save, then pick the
users whose viewing counts. Keys:

- **Emby**: Settings → Advanced → API keys → new key.
- **Jellyfin**: Dashboard → API keys → new key.
- **Plex**: the X-Plex-Token of the server owner (Plex support article "Finding an
  authentication token"). Finalarr reads each account's history through it, so Plex Home
  managed users work without their PIN.

Finalarr matches watched series to Sonarr by TVDB id; series without one, or missing in
Sonarr, are listed as unmatched and never added to Sonarr. It stores per selected user only
which episodes were watched and on which day.

## Connect Sonarr

1. Open Finalarr, sign in with the API key, follow the setup.
2. Copy the webhook URL from *Settings → Sonarr* into Sonarr under
   *Settings → Connect → Webhook* (method POST; events On Import, On Upgrade,
   On Series Add, On Episode File Delete). Basic auth is optional and supported.
3. The webhook only speeds things up; Finalarr also syncs every 30 minutes.

## Notifications

Add a channel under *Settings → Channels* (Telegram, Discord, Pushover, webhook or
any Apprise URL) and send a test message. Channel URLs are stored encrypted and never
shown again.

Each event is created once, and each channel gets it once. A message is marked as sent
only after the channel accepted it, so if Finalarr stops between the two, or a backup
older than the message is restored, that message can arrive a second time. A send that
fails is tried again after one and after five minutes; after the third failure it is
marked failed, and *Events* shows it with the channel's error.

## Where announcements come from

| Source | Covers | Key |
|---|---|---|
| Sonarr / TheTVDB | a season once TVDB lists its episodes | — |
| AniList (+ Fribb mapping) | anime counts, split cours, sequels before TVDB knows them | — |
| MyAnimeList via Jikan | second source for anime sequels | — |
| TVmaze | renewed TV seasons, often months early | — |
| TMDB | same, second source | `FINALARR_TMDB_API_KEY` |
| Trakt | same, third source | `FINALARR_TRAKT_CLIENT_ID` |
| LiveChart.me, Anime News Network, Anime2You, Crunchyroll News (RSS) | headlines that name a followed series (typed hint with link) | — |
| Google News (RSS search) | latest headlines in the news box of a series page | — |
| AniList / TVmaze | next episode, channel, streaming links, trailer on the series page | — |
| TMDB | "where to watch" per country (JustWatch data), trailer | `FINALARR_TMDB_API_KEY`, `FINALARR_WATCH_REGION` (default `DE`) |
| AnimeSchedule.net | English dub dates and delay notes | `FINALARR_ANIMESCHEDULE_TOKEN` |

Every source reports a season or sequel under the same key, so you get one message no
matter which one knows first. News hints can be switched off under *Settings → Rules*.

## Calendar feed

*Settings → Calendar* switches on an iCal feed at `/ical/<token>.ics` (add `?lang=en`
for English titles). Subscribe to it in any calendar app. The token is the only
protection: keep the address private, renew it to revoke old subscriptions. Google and Outlook fetch
the feed from their own servers, so it must be reachable from the internet. Expose **only**
`/ical/` through your reverse proxy (everything else 404), set `FINALARR_FEED_URL` to that
public base so the settings show the right address, and set `FINALARR_TRUSTED_PROXIES` so
proxied requests never count as local. Example for nginx:

```nginx
location / { return 404; }
location /ical/ {
    limit_except GET HEAD { deny all; }
    proxy_pass http://finalarr:5790;
}
```
