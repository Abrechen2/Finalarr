"""In-memory Sonarr for reconciler and integration tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from finalarr.sources.sonarr import SonarrEpisode, SonarrSeries, SonarrUnreachable

BASE_AIR = datetime(2026, 1, 5, 15, tzinfo=UTC)


def make_series(
    sid: int, title: str, seasons=(1,), series_type="standard", tags=()
) -> SonarrSeries:
    return SonarrSeries.model_validate(
        {
            "id": sid,
            "title": title,
            "titleSlug": title.lower().replace(" ", "-"),
            "tvdbId": 1000 + sid,
            "seriesType": series_type,
            "seasons": [{"seasonNumber": n, "monitored": True} for n in seasons],
            "images": [{"coverType": "poster", "remoteUrl": f"https://img/{sid}.jpg"}],
            "tags": list(tags),
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
        self.tag_labels: dict[int, str] = {}

    def add(self, series: SonarrSeries, episodes=()) -> None:
        self.series_by_id[series.id] = series
        self.episodes_by_series[series.id] = list(episodes)

    def _check(self, call: str) -> None:
        self.calls.append(call)
        if self.down:
            raise SonarrUnreachable("Sonarr cannot be reached")

    def tags(self):
        self._check("tags")
        return dict(self.tag_labels)

    def series_list(self):
        self._check("series_list")
        return list(self.series_by_id.values())

    def series(self, series_id: int):
        self._check(f"series:{series_id}")
        return self.series_by_id[series_id]

    def episodes(self, series_id: int):
        self._check(f"episodes:{series_id}")
        return list(self.episodes_by_series.get(series_id, []))


class FakeAnilist:
    """AniList stand-in serving media from the recorded batch fixture."""

    def __init__(self, media=None) -> None:
        import json
        from pathlib import Path

        from finalarr.sources.anilist import AnilistMedia

        if media is None:
            raw = json.loads(
                (Path(__file__).parent / "fixtures/anilist/media_batch.json").read_text()
            )
            media = [AnilistMedia.model_validate(m) for m in raw["data"]["Page"]["media"]]
        self.media = {m.id: m for m in media}
        self.batches: list[list[int]] = []
        self.searches: list[str] = []
        self.error: Exception | None = None

    def media_batch(self, ids):
        self.batches.append(list(ids))
        if self.error:
            raise self.error
        return {i: self.media[i] for i in ids if i in self.media}

    def search(self, text):
        self.searches.append(text)
        if self.error:
            raise self.error
        return [m for m in self.media.values() if text.lower() in m.title.lower()]


class FakeSender:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []
        self.fail_with: str | None = None

    def send(self, url: str, body: str) -> None:
        from finalarr.notify.sender import SendError

        if self.fail_with:
            raise SendError(self.fail_with)
        self.sent.append((url, body))
