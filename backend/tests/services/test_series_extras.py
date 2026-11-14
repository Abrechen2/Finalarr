from datetime import UTC, datetime, timedelta

import pytest

from finalarr.db import models as m
from finalarr.db.session import Database
from finalarr.services.season_sources import JsonCache
from finalarr.services.series_extras import ExtrasSources, series_extras
from finalarr.sources.anilist import AnilistError, AnilistMedia
from finalarr.sources.animeschedule import AnimeScheduleError, DubInfo
from finalarr.sources.tmdb import TmdbExtras
from finalarr.sources.tvmaze import TvmazeError, TvmazeShow

NOW = datetime(2026, 11, 14, 12, tzinfo=UTC)


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "f.db")
    database.migrate()
    with database.session() as s:
        instance = m.SonarrInstance(name="C", url="http://s:1", api_key_enc="x", webhook_token="t")
        slime = m.Series(
            instance=instance,
            sonarr_id=1,
            tvdb_id=100,
            title="Slime",
            series_type="anime",
            network="Tokyo MX",
            followed=True,
        )
        season = m.Season(number=4)
        season.episodes += [
            m.Episode(sonarr_episode_id=1, number=1, air_date_utc=NOW - timedelta(days=7)),
            m.Episode(sonarr_episode_id=2, number=2, air_date_utc=None),
        ]
        slime.seasons.append(season)
        s.add(slime)
        s.add_all(
            [
                m.AnilistMapping(tvdb_id=100, tvdb_season=3, anilist_id=30),
                m.AnilistMapping(tvdb_id=100, tvdb_season=4, anilist_id=40),
                m.FribbId(anilist_id=40, mal_id=400),
            ]
        )
        s.commit()
    yield database
    database.dispose()


def media(next_at=None):
    return AnilistMedia.model_validate(
        {
            "id": 40,
            "title": {"romaji": "Slime 4"},
            "nextAiringEpisode": {"episode": 2, "airingAt": int(next_at.timestamp())}
            if next_at
            else None,
            "trailer": {"id": "yt40", "site": "youtube"},
            "externalLinks": [
                {"site": "Crunchyroll", "url": "https://cr/slime", "type": "STREAMING"}
            ],
        }
    )


class FakeAnilist:
    def __init__(self, result=None, error=False):
        self.result, self.error, self.asked = result or {}, error, []

    def media(self, ids):
        self.asked.append(ids)
        if self.error:
            raise AnilistError("down")
        return self.result


class FakeTvmaze:
    def __init__(self, show=None, error=False):
        self._show, self.error, self.calls = show, error, 0

    def show_id_for_tvdb(self, tvdb_id):
        if self.error:
            raise TvmazeError("down")
        return 9

    def show(self, show_id):
        self.calls += 1
        return self._show


class FakeTmdb:
    def tv_id_for_tvdb(self, tvdb_id):
        return 5

    def extras(self, tv_id, region):
        return TmdbExtras("tmdbtrailer", ("Crunchyroll", "Netflix"), "https://tmdb/watch")


class FakeSchedule:
    def __init__(self, error=False):
        self.error = error

    def by_mal_id(self, mal_id):
        if self.error:
            raise AnimeScheduleError("down")
        assert mal_id == 400
        return DubInfo(route="slime", dubTime=NOW + timedelta(days=3))


def extras(db, **kwargs):
    sources = ExtrasSources(cache=JsonCache(db, clock=lambda: NOW), **kwargs)
    with db.session() as s:
        return series_extras(s, s.query(m.Series).one(), sources, NOW)


def test_anilist_fills_next_episode_trailer_and_streaming(db):
    anilist = FakeAnilist({40: media(NOW + timedelta(days=2))})
    show = TvmazeShow.model_validate({"webChannel": {"name": "Crunchyroll"}})
    result = extras(db, tvmaze=FakeTvmaze(show), anilist=anilist)
    assert anilist.asked == [[40]]
    assert result["next_episode"] == {
        "season": 4,
        "episode": 2,
        "at": (NOW + timedelta(days=2)).isoformat(),
        "source": "anilist",
    }
    assert result["trailer"] == {"youtube_id": "yt40"}
    assert result["watch"] == [
        {"name": "Crunchyroll", "url": "https://cr/slime", "source": "anilist"}
    ]
    assert result["channel"] == "Crunchyroll"
    assert result["errors"] == []
    assert result["dub"] is None


def test_sonarr_date_wins_and_tmdb_adds_providers(db):
    with db.session() as s:
        s.query(m.Episode).filter_by(number=2).one().air_date_utc = NOW + timedelta(days=1)
        s.commit()
    result = extras(
        db,
        tvmaze=FakeTvmaze(TvmazeShow.model_validate({})),
        anilist=FakeAnilist({40: media(NOW + timedelta(days=2))}),
        tmdb=FakeTmdb(),
        animeschedule=FakeSchedule(),
    )
    assert result["next_episode"]["source"] == "sonarr"
    assert result["next_episode"]["episode"] == 2
    assert [w["name"] for w in result["watch"]] == ["Crunchyroll", "Netflix"]
    assert result["watch"][1] == {"name": "Netflix", "url": "https://tmdb/watch", "source": "tmdb"}
    assert result["watch_region"] == "DE"
    assert result["channel"] == "Tokyo MX"
    assert result["dub"]["next"] == (NOW + timedelta(days=3)).isoformat()
    assert result["dub"]["url"] == "https://animeschedule.net/anime/slime"


def test_tvmaze_next_episode_and_tmdb_trailer_as_fallbacks(db):
    show = TvmazeShow.model_validate(
        {
            "network": {"name": "Tokyo MX"},
            "_embedded": {
                "nextepisode": {"season": 4, "number": 2, "airstamp": "2026-11-20T15:00:00+00:00"}
            },
        }
    )
    tvmaze = FakeTvmaze(show)
    result = extras(db, tvmaze=tvmaze, tmdb=FakeTmdb())
    assert result["next_episode"]["source"] == "tvmaze"
    assert result["trailer"] == {"youtube_id": "tmdbtrailer"}
    extras(db, tvmaze=tvmaze, tmdb=FakeTmdb())
    assert tvmaze.calls == 1  # cached


def test_failing_sources_are_named(db):
    result = extras(
        db,
        tvmaze=FakeTvmaze(error=True),
        anilist=FakeAnilist(error=True),
        animeschedule=FakeSchedule(error=True),
    )
    assert result["errors"] == ["anilist", "tvmaze", "animeschedule"]
    assert (result["next_episode"], result["trailer"], result["watch"]) == (None, None, [])


def test_past_remote_dates_are_ignored(db):
    show = TvmazeShow.model_validate(
        {
            "_embedded": {
                "nextepisode": {"season": 4, "number": 2, "airstamp": "2026-11-01T00:00:00Z"}
            }
        }
    )
    assert extras(db, tvmaze=FakeTvmaze(show))["next_episode"] is None


def test_anime_typed_standard_still_uses_its_anilist_mapping(db):
    with db.session() as s:
        s.query(m.Series).one().series_type = "standard"
        s.commit()
    anilist = FakeAnilist({40: media()})
    assert extras(db, tvmaze=None, anilist=anilist)["trailer"] == {"youtube_id": "yt40"}
    assert anilist.asked == [[40]]


def test_series_without_mapping_skips_anilist(db):
    with db.session() as s:
        s.query(m.AnilistMapping).delete()
        s.commit()
    anilist = FakeAnilist()
    extras(db, tvmaze=None, anilist=anilist)
    assert anilist.asked == []
