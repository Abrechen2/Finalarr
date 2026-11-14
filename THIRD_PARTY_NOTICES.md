# Third-party notices

Finalarr is licensed under the GNU General Public License v3.0 only (see `LICENSE`).
It includes or depends on the following third-party work.

## Fonts (SIL Open Font License 1.1)

- **Unbounded** — Copyright 2022 The Unbounded Project Authors
  (https://github.com/googlefonts/unbounded)
- **Atkinson Hyperlegible Next** — Copyright 2024 Braille Institute of America, Inc.

Both are bundled through `@fontsource-variable` and served by Finalarr itself. The full
licence texts ship with the image.

## Icons

- **Lucide** (`lucide-react`) — ISC licence; parts derived from Feather, MIT licence.

## Code dependencies

- Frontend: React, React Router, TanStack Query, i18next and others, mostly MIT/ISC.
- Backend: Flask, SQLAlchemy, Alembic, APScheduler, pydantic, requests, Apprise,
  cryptography, icalendar, defusedxml, gunicorn and others under MIT, BSD, Apache-2.0
  or similar permissive licences.

Where to find the full texts in the Docker image:
- Frontend packages and fonts: `/app/static/licenses/`, with `INDEX.txt` listing every
  package, its version and its licence. Also reachable at `<your Finalarr>/licenses/INDEX.txt`.
- Python packages: the `*.dist-info/` folders in the Python `site-packages` directory.

## Artwork

The Finalarr mark and icon (`assets/`) were made for this project and are licensed
under GPL-3.0 like the code. The `<abrechen2 />` wordmark
(`frontend/src/assets/abrechen2-wordmark.svg`) belongs to the maintainer and is only
used as the project credit. Forks should keep the credit or remove the mark; they must
not use it as their own brand.

## Data sources

Finalarr only queries metadata services at runtime and stores none of their data in the
repository: Sonarr (your instance), AniList, Fribb's anime-lists, Jikan/MyAnimeList,
TVmaze, TMDB ("This product uses the TMDB API but is not endorsed or certified by TMDB";
streaming offers by JustWatch), Trakt, AnimeSchedule.net, and the RSS feeds named in the
README.
