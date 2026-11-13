from datetime import UTC, date, datetime, timedelta

import pytest

from finalarr.db.session import Database
from finalarr.services.announcements import Announced, SourceError
from finalarr.services.season_sources import JsonCache, TmdbSource, TraktSource, TvmazeSource
from finalarr.sources.tmdb import TmdbError
from finalarr.sources.tvmaze import TvmazeError, TvmazeSeason

NOW = datetime(2026, 11, 13, tzinfo=UTC)


@pytest.fixture
def cache(tmp_path):
    db = Database(tmp_path / "f.db")
    db.migrate()
    clock = {"now": NOW}
    yield JsonCache(db, clock=lambda: clock["now"]), clock
    db.dispose()


class FakeTvmaze:
    def __init__(self):
        self.calls = []
        self.error = None

    def show_id_for_tvdb(self, tvdb_id):
        self.calls.append(("lookup", tvdb_id))
        if self.error:
            raise self.error
        return 44933 if tvdb_id == 371980 else None

    def seasons(self, show_id):
        self.calls.append(("seasons", show_id))
        return [TvmazeSeason(number=3, premiereDate=None, episodeOrder=None)]


def test_tvmaze_source_maps_and_caches(cache):
    json_cache, clock = cache
    client = FakeTvmaze()
    source = TvmazeSource(client, json_cache)
    assert source.seasons(371980) == [Announced(3, None, None)]
    assert source.seasons(371980) == [Announced(3, None, None)]
    assert source.seasons(1) == []
    assert source.seasons(1) == []
    assert client.calls == [("lookup", 371980), ("seasons", 44933), ("lookup", 1)]
    clock["now"] += timedelta(hours=13)  # season list expired, lookup still cached
    source.seasons(371980)
    assert client.calls[-1] == ("seasons", 44933)


def test_tvmaze_errors_become_source_errors(cache):
    client = FakeTvmaze()
    client.error = TvmazeError("down")
    with pytest.raises(SourceError):
        TvmazeSource(client, cache[0]).seasons(371980)


class FakeRowsClient:
    def __init__(self, error=None):
        self.error = error

    def tv_id_for_tvdb(self, tvdb_id):
        if self.error:
            raise self.error
        return 9

    show_id_for_tvdb = tv_id_for_tvdb

    def seasons(self, _id):
        return [(3, date(2027, 3, 5), 10)]


def test_tmdb_and_trakt_sources(cache):
    assert TmdbSource(FakeRowsClient(), cache[0]).seasons(5) == [Announced(3, date(2027, 3, 5), 10)]
    assert TraktSource(FakeRowsClient(), cache[0]).seasons(5) == [
        Announced(3, date(2027, 3, 5), 10)
    ]
    with pytest.raises(SourceError):
        TmdbSource(FakeRowsClient(error=TmdbError("401")), cache[0]).seasons(6)
