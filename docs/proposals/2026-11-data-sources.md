# More data for "what am I waiting for" — proposals (2026-11-14)

Research: own checks against the live APIs (results below are verified, not assumed) and
an independent pass by Codex. Gemini was asked as well but its service answered 503/404
twice, so it is not part of this round.

## Verified building blocks

| Source | What it gives | Access | Checked |
|---|---|---|---|
| AniList `airingSchedule` | exact air time per anime episode | free, no key | yes |
| AniList `externalLinks` (STREAMING) | Crunchyroll, Netflix, … per anime | free, no key | yes |
| AniList `trailer` | YouTube id of the official PV/trailer | free, no key | yes |
| TVmaze show `network` / `webChannel`, `nextepisode` | channel or streamer, next airstamp | free, no key | yes |
| Anime2You RSS (`/feed/`) | German anime news | RSS, no key | yes |
| Crunchyroll News RSS | English anime news | RSS, no key | yes |
| Own data (Sonarr + AniList dates per run) | air dates that moved → delays, hiatus | — | design |
| TMDB watch providers | streaming services per country (JustWatch data) | user key, attribution | 401 without key |
| AnimeSchedule.net API | sub/dub times, delay notes | user token, ToS: attribution, no bulk mirroring | 401 without token |

## Proposals, best value first

| # | Proposal | Shown where | Source | Effort |
|---|---|---|---|---|
| 1 | **"Episode postponed" detection**: compare stored air dates on every sync; a moved date or a gap becomes `episode_delayed` (old → new date), the calendar moves the entry and marks it | notification, calendar, series page | own data + AniList schedule | M |
| 2 | **Next episode with countdown and exact time** ("Folge 24 in 3 Tagen, Sa 17:00") | series page, dashboard | AniList schedule, TVmaze nextepisode, Sonarr | S |
| 3 | **Trailer on the series page**, loaded only after a click (youtube-nocookie, no request before) | series page | AniList trailer id; TMDB videos with key | S |
| 4 | **"Where to watch" chips** (Crunchyroll, Netflix, Apple TV, …); per country with a TMDB key | series page, calendar entry | AniList links, TVmaze channel, TMDB providers | S–M |
| 5 | **Two more news feeds**: Anime2You (DE), Crunchyroll News (EN), through the new season/episode filter | news box, hints | RSS | XS |
| 6 | **Waiting-state card** per series: "renewed, date open", "cour 2 announced", "3 episodes missing locally", "count disputed" — one sentence instead of scattered badges | series page, series list | data Finalarr already has | M |
| 7 | **Richer series header** from Sonarr: overview, network, runtime, genres, fanart | series page | Sonarr (already fetched) | S |
| 8 | **AnimeSchedule.net (optional token)**: German dub dates and delay notes | calendar track "Dub", notifications | AnimeSchedule API | M |
| 9 | **Typed news events** (announcement, renewal, cancellation, delay, trailer) instead of plain hints, with the matched sentence as evidence; later a small local classifier | news box, notifications | existing feeds | L |

## Not recommended

- JustWatch scraping (terms forbid it; TMDB's licensed provider data covers the need).
- YouTube Data API (daily quota; AniList already names the trailer).
- Watchmode (free tier is three countries and non-commercial).
- Scraping broadcaster or Netflix newsrooms (fragile, unclear reuse rights).

## Notes on the news filter (now live)

Rules keep a headline only if it names the series and talks about seasons, episodes,
premieres, finales, renewals, cancellations, delays or trailers, and drop merchandise,
films, manga, games, events, songs, listicles and reviews. Codex's caveat applies: a
headline like "season 2 announced alongside figures" is dropped too; #9 would fix that by
judging the sentence, not the headline.
