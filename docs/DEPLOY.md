# Deploying Finalarr

## Requirements

- Docker with Compose, amd64 (arm64 images come with final releases).
- Sonarr v4 reachable from the container.
- Two secrets in the environment (Finalarr refuses to start without them):
  - `FINALARR_API_KEY` — at least 20 characters, e.g. `openssl rand -hex 32`. It is also
    the UI login.
  - `FINALARR_SECRET_KEY` — a Fernet key:
    `python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`.
    It encrypts stored Sonarr keys and channel URLs; changing it makes them unreadable.

Optional: `FINALARR_AUTH=local` (no login from home networks, like Sonarr's "disabled for
local addresses"; behind a reverse proxy also set `FINALARR_TRUSTED_PROXIES`, or every
request looks local), `FINALARR_PUBLIC_URL` (adds "Finalarr" links to messages),
`FINALARR_TRUSTED_PROXIES` (number of reverse proxies in front),
`FINALARR_WEBHOOK_ALLOW` (IPs/CIDRs allowed to call the webhook), `PUID`/`PGID`, `TZ`.
See `.env.example`.

## Docker Compose

```sh
cp .env.example .env   # fill in the two keys
docker compose up -d --build
```

Data lives in `/config` (SQLite database, log, scheduler lock). Back it up like any
other appdata folder.

## Unraid

Use `docker-compose.unraid.yml` as an overlay (`PUID=99`, `PGID=100`, appdata path,
env file) or create a container from the image with the same settings. To ship an image
built elsewhere: `DEPLOY_HOST=root@unraid scripts/deploy.sh [--rc N]` builds amd64,
loads it over SSH, restarts the container and waits for `/health`. It asks before
restarting.

## Connect Sonarr

1. Open Finalarr, sign in with the API key, follow the setup.
2. Copy the webhook URL from *Einstellungen → Sonarr* into Sonarr under
   *Settings → Connect → Webhook* (method POST; events On Import, On Upgrade,
   On Series Add, On Episode File Delete). Basic auth is optional and supported.
3. The webhook only speeds things up; Finalarr also syncs every 30 minutes.

## Notifications

Add a channel under *Einstellungen → Kanäle* (Telegram, Discord, Pushover, webhook or
any Apprise URL) and send a test message. Channel URLs are stored encrypted and never
shown again.

## Where announcements come from

| Source | Covers | Key |
|---|---|---|
| Sonarr / TheTVDB | a season once TVDB lists its episodes | — |
| AniList (+ Fribb mapping) | anime counts, split cours, sequels before TVDB knows them | — |
| MyAnimeList via Jikan | second source for anime sequels | — |
| TVmaze | renewed TV seasons, often months early | — |
| TMDB | same, second source | `FINALARR_TMDB_API_KEY` |
| Trakt | same, third source | `FINALARR_TRAKT_CLIENT_ID` |
| LiveChart.me, Anime News Network (RSS) | headlines that name a followed series (hint with link) | — |

Every source reports a season or sequel under the same key, so you get one message no
matter which one knows first. News hints can be switched off under *Einstellungen → Regeln*.

## Calendar feed

*Einstellungen → Kalender* switches on an iCal feed at `/ical/<token>.ics` (add `?lang=en`
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
