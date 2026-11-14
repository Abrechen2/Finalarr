# Follow by watching — Emby, Jellyfin, Plex (design for 0.4, 2026-11-14)

Goal: Finalarr reads what the household actually watches on Emby, Jellyfin and Plex,
follows those series automatically and shows watched state in the UI. All three servers
are in scope from the first version. Design drafted with Codex, checked against the code.

## Connecting the servers

| Server | Auth | Watched episodes per user | Series id for Sonarr |
|---|---|---|---|
| Emby | API key (`X-Emby-Token`) | `/Users/{id}/Items?Recursive=true&IncludeItemTypes=Episode&IsPlayed=true&Fields=ProviderIds` → `UserData.Played`, `LastPlayedDate` | parent series `ProviderIds.Tvdb` |
| Jellyfin | API key (`X-Emby-Token`) | `/Items?UserId=…&Recursive=true&IncludeItemTypes=Episode&IsPlayed=true&EnableUserData=true&Fields=ProviderIds` | same; own adapter, API drifts from Emby |
| Plex | `X-Plex-Token` (owner) | per-user section listing `type=4` (`viewCount`, `lastViewedAt`) plus `/status/sessions/history/all?accountID=…` for recent plays | show `includeGuids=1` → `tvdb://…`; never treat `plex://` as TVDB |

- Users are listed per server and **selected explicitly** (family members, Plex Home managed
  users). Plex Home managed users have no own login: history comes through the owner token
  or a Home switch; PINs are never stored.
- Matching only by TVDB id against Sonarr series; duplicates or missing ids stay
  "unmatched" and are shown, never guessed, never added to Sonarr.
- Paging 500 items per request, no images, show metadata cached.

## Sync

- Poll every 30 minutes (recent plays first, with overlap), full reconciliation nightly.
  Webhooks later, only as a speed-up.
- A partial or failed scan marks state "unknown", never "unwatched".
- Store only: opaque user/item ids, per-user watched episodes (Sonarr episode ids),
  last activity per series and user, sync checkpoints. Tokens encrypted (`SecretBox`).
  No viewing log, no positions, devices, IPs or raw payloads; disconnecting a user deletes
  their data.

## Follow rule

- `Series.follow_mode = auto | always | never`; `followed = always OR (auto AND any
  selected user qualifies)`.
- Default rule (opt-in, adjustable): at least 2 distinct regular episodes watched within
  30 days by any selected user.
- Manual follow stays `always`, manual unfollow becomes `never`, with "back to automatic".
  Follow-by-tag and "follow all monitored" write `always`, but respect `never`.
- Migration: today's followed series become `always`, the rest `auto`; automation stays
  off until a server is connected.
- Newly auto-followed series start with the silent baseline as today (no backlog flood).
- Later: optional auto-drop after 180 days without watching while unwatched episodes exist.

## UI (owner requirement)

- **Episode grid:** watched episodes get their own mark (e.g. a check in the square; colour
  meanings in docs/DESIGN.md stay: rose = on disk, gold = finale). Tooltip names who
  watched it in multi-user households.
- **Series page:** "Gesehen: 7 von 12 (Dennis), 3 von 12 (Anna)", last watched, why the
  series is followed ("automatisch: 4 Folgen in den letzten 30 Tagen" / "manuell" /
  "nie folgen"), switch between automatic, always and never.
- **Series list:** filters "angefangen", "auf dem neuesten Stand", "automatisch gefolgt",
  "nicht zugeordnet"; watched progress next to the on-disk progress.
- **Waiting card:** "Du bist auf dem neuesten Stand – nächste Folge Sa. 17:00" or
  "3 Folgen ungesehen".
- **Settings → Mediaserver:** add Emby/Jellyfin/Plex (URL, key, connection test), pick
  users, see last sync, unmatched series and errors; follow rule thresholds.
- **Dashboard:** "Weiterschauen" column: followed series with unwatched episodes on disk.

## "Only when caught up" (later)

Opt-in per channel: a "new episodes" message only goes to someone who has watched every
episode that was available before this batch. Lives in delivery (`services/delivery.py`),
not in the pure evaluator; deferred messages wait up to 7 days, already watched ones are
dropped. Needs reliable episode mapping first (anime absolute numbering, specials,
multi-episode files), so it is not part of the first version.

## Where it lands

- `sources/media/{base,emby,jellyfin,plex}.py` — adapters, normalised to users, series ids,
  watched episodes, last played.
- `services/watch_sync.py` (scheduler job), `services/auto_follow.py` (rule).
- `api/media_servers.py` (setup, test, users, status); `api/series.py` (follow mode,
  watched state in detail and list).
- Migration: media servers, selected users, item mappings, per-user watched episodes,
  per-series interest, checkpoints; `Series.follow_mode`.
- Rename `reconciler.series_watched()` to `series_initialized()` — today it means "already
  evaluated", which will be confusing next to real watch state.
- Fixtures per server version; tests for revoked tokens, paging, rewatches (distinct
  episodes, not play counts), mark-as-watched imports.

## First version (0.4)

All three servers, selected users, polling, TVDB matching, follow modes and the UI above.
Later: webhooks, auto-drop, fuzzy matching, complex anime episode mapping, "only when
caught up".
