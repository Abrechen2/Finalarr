from datetime import UTC, datetime, timedelta

import pytest

from finalarr.db import models as m
from finalarr.db.session import Database
from finalarr.services.count_sources import count_sources
from finalarr.services.season_sources import JsonCache
from finalarr.sources.anilist import AnilistError, AnilistMedia

NOW = datetime(2026, 11, 14, tzinfo=UTC)


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "f.db")
    database.migrate()
    with database.session() as s:
        instance = m.SonarrInstance(
            name="H", url="http://sonarr:8989", api_key_enc="x", webhook_token="t"
        )
        series = m.Series(
            instance=instance,
            sonarr_id=1,
            tvdb_id=100,
            title="Mushoku",
            title_slug="mushoku",
            followed=True,
        )
        season = m.Season(
            number=2,
            anilist_count=24,
            expected_count=24,
            expected_source="anilist",
            disputed=True,
            state="aired",
        )
        season.episodes += [
            m.Episode(
                sonarr_episode_id=n,
                number=n,
                has_file=n <= 10,
                air_date_utc=NOW - timedelta(days=30 - n),
                finale_type="season" if n == 12 else None,
            )
            for n in range(1, 13)
        ]
        season.parts += [
            m.AnimePart(part_index=1, anilist_id=10, episode_from=1, episode_to=12, title="Part 1"),
            m.AnimePart(
                part_index=2, anilist_id=11, episode_from=13, episode_to=24, title="Part 2"
            ),
        ]
        series.seasons.append(season)
        s.add(series)
        s.add_all(
            [
                m.AnilistMapping(tvdb_id=100, tvdb_season=2, anilist_id=10),
                m.AnilistMapping(tvdb_id=100, tvdb_season=2, anilist_id=11),
            ]
        )
        s.commit()
    yield database
    database.dispose()


def media(media_id, episodes, status):
    return AnilistMedia.model_validate(
        {
            "id": media_id,
            "title": {"english": f"Mushoku S2 P{media_id - 9}"},
            "episodes": episodes,
            "status": status,
        }
    )


class Anilist:
    def __init__(self, error=False):
        self.error = error

    def media(self, ids):
        if self.error:
            raise AnilistError("down")
        return {10: media(10, 12, "FINISHED"), 11: media(11, 12, "NOT_YET_RELEASED")}


def sources(db, anilist=None):
    cache = JsonCache(db, clock=lambda: NOW)
    cache.put("tvmaze:show:100", 7, timedelta(days=1))
    cache.put("tvmaze:seasons:7", [[1, "2021-01-10", 11], [2, "2023-07-03", 25]], timedelta(days=1))
    with db.session() as s:
        season = s.query(m.Season).one()
        return count_sources(s, season.series, season, cache, anilist or Anilist())


def test_every_source_with_its_number_and_the_decision(db):
    result = sources(db)
    assert (result["expected"], result["expected_source"], result["disputed"]) == (
        24,
        "anilist",
        True,
    )
    by = {row["source"]: row for row in result["sources"]}
    assert by["sonarr"]["count"] == 12
    assert by["sonarr"]["detail"] == {"listed": 12, "aired": 12, "on_disk": 10, "finale": 12}
    assert by["sonarr"]["url"] == "http://sonarr:8989/series/mushoku"
    assert by["anilist"]["count"] == 24
    assert by["anilist"]["entries"] == [
        {
            "id": 10,
            "title": "Mushoku S2 P1",
            "episodes": 12,
            "status": "FINISHED",
            "url": "https://anilist.co/anime/10",
        },
        {
            "id": 11,
            "title": "Mushoku S2 P2",
            "episodes": 12,
            "status": "NOT_YET_RELEASED",
            "url": "https://anilist.co/anime/11",
        },
    ]
    assert by["anilist"]["parts"] == [
        {"index": 1, "from": 1, "to": 12, "title": "Part 1"},
        {"index": 2, "from": 13, "to": 24, "title": "Part 2"},
    ]
    assert by["tvmaze"] == {
        "source": "tvmaze",
        "count": 25,
        "url": "https://www.tvmaze.com/shows/7",
    }
    assert "override" not in by


def test_override_and_anilist_down(db):
    with db.session() as s:
        s.query(m.Season).one().expected_override = 23
        s.commit()
    by = {row["source"]: row for row in sources(db, Anilist(error=True))["sources"]}
    assert by["override"]["count"] == 23
    assert by["anilist"]["entries"] == [
        {
            "id": 10,
            "title": None,
            "episodes": None,
            "status": None,
            "url": "https://anilist.co/anime/10",
        },
        {
            "id": 11,
            "title": None,
            "episodes": None,
            "status": None,
            "url": "https://anilist.co/anime/11",
        },
    ]
