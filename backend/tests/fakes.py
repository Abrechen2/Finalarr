"""In-memory Sonarr for reconciler and integration tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from finalarr.sources.sonarr import SonarrEpisode, SonarrSeries, SonarrUnreachable

BASE_AIR = datetime(2026, 1, 5, 15, tzinfo=UTC)


def make_series(sid: int, title: str, seasons=(1,), series_type="standard") -> SonarrSeries:
    return SonarrSeries.model_validate(
        {
            "id": sid,
            "title": title,
            "titleSlug": title.lower().replace(" ", "-"),
            "tvdbId": 1000 + sid,
            "seriesType": series_type,
            "seasons": [{"seasonNumber": n, "monitored": True} for n in seasons],
            "images": [{"coverType": "poster", "remoteUrl": f"https://img/{sid}.jpg"}],
        }
    )


def make_episodes(series_id: int, season: int, count: int, files: set[int], **extra):
    return [
        SonarrEpisode.model_validate(
            {
                "id": series_id * 1000 + season * 100 + n,
                "seriesId": series_id,
                "seasonNumber": season,
                "episodeNumber": n,
                "title": f"Episode {n}",
                "airDateUtc": (BASE_AIR + timedelta(days=7 * (n - 1))).isoformat(),
                "monitored": True,
                "hasFile": n in files,
                **extra.get(n, {}),
            }
        )
        for n in range(1, count + 1)
    ]


class FakeSonarr:
    def __init__(self) -> None:
        self.series_by_id: dict[int, SonarrSeries] = {}
        self.episodes_by_series: dict[int, list[SonarrEpisode]] = {}
        self.calls: list[str] = []
        self.down = False

    def add(self, series: SonarrSeries, episodes=()) -> None:
        self.series_by_id[series.id] = series
        self.episodes_by_series[series.id] = list(episodes)

    def _check(self, call: str) -> None:
        self.calls.append(call)
        if self.down:
            raise SonarrUnreachable("Sonarr cannot be reached")

    def series_list(self):
        self._check("series_list")
        return list(self.series_by_id.values())

    def series(self, series_id: int):
        self._check(f"series:{series_id}")
        return self.series_by_id[series_id]

    def episodes(self, series_id: int):
        self._check(f"episodes:{series_id}")
        return list(self.episodes_by_series.get(series_id, []))
