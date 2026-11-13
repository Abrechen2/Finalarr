#!/usr/bin/env python3
"""Save sanitised Sonarr responses as test fixtures (read-only GETs).

Usage: SONARR_URL=http://... SONARR_API_KEY=... \
       scripts/capture-sonarr-fixtures.py "Slime" "Mushoku" [...]

Writes backend/tests/fixtures/sonarr/real/<slug>.json with the series and
its episodes. Only the fields Finalarr reads are kept, so no paths, file
names, overviews or keys end up in git.
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

SERIES_FIELDS = ("id", "title", "sortTitle", "titleSlug", "year", "tvdbId", "seriesType", "status", "monitored")
EPISODE_FIELDS = (
    "id", "seriesId", "seasonNumber", "episodeNumber", "absoluteEpisodeNumber",
    "title", "airDateUtc", "monitored", "hasFile", "finaleType",
)
OUT = Path(__file__).resolve().parents[1] / "backend/tests/fixtures/sonarr/real"


def get(base: str, key: str, path: str) -> object:
    request = urllib.request.Request(base.rstrip("/") + path, headers={"X-Api-Key": key})
    with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 - operator-supplied URL
        return json.load(response)


def main() -> int:
    base, key = os.environ.get("SONARR_URL"), os.environ.get("SONARR_API_KEY")
    if not base or not key or len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    wanted = [w.lower() for w in sys.argv[1:]]
    OUT.mkdir(parents=True, exist_ok=True)
    for series in get(base, key, "/api/v3/series"):  # type: ignore[union-attr]
        if not any(w in series["title"].lower() for w in wanted):
            continue
        episodes = get(base, key, f"/api/v3/episode?seriesId={series['id']}")
        record = {
            "series": {k: series.get(k) for k in SERIES_FIELDS}
            | {"seasons": [{"seasonNumber": s["seasonNumber"], "monitored": s["monitored"]} for s in series["seasons"]]},
            "episodes": [{k: e.get(k) for k in EPISODE_FIELDS if k in e} for e in episodes],  # type: ignore[union-attr]
        }
        path = OUT / f"{series['titleSlug']}.json"
        path.write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {path.relative_to(OUT.parents[3])} ({len(record['episodes'])} episodes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
