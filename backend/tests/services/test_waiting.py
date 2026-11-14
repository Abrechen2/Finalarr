import json
from datetime import UTC, datetime, timedelta

import pytest

from finalarr.db import models as m
from finalarr.db.session import Database
from finalarr.services.waiting import waiting_state

NOW = datetime(2026, 11, 14, 12, tzinfo=UTC)


def ep(number, days, has_file):
    return m.Episode(
        sonarr_episode_id=number,
        number=number,
        air_date_utc=NOW + timedelta(days=days),
        has_file=has_file,
    )


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "f.db")
    database.migrate()
    with database.session() as s:
        instance = m.SonarrInstance(name="C", url="http://s:1", api_key_enc="x", webhook_token="t")
        series = m.Series(instance=instance, sonarr_id=1, title="Slime", followed=True)
        season = m.Season(number=2, state="airing", expected_count=4)
        season.episodes += [ep(1, -14, True), ep(2, -7, True), ep(3, 7, False), ep(4, 14, False)]
        series.seasons += [m.Season(number=1, state="complete"), season]
        s.add(series)
        s.commit()
    yield database
    database.dispose()


def state(db, change=None):
    with db.session() as s:
        series = s.query(m.Series).one()
        if change:
            change(s, series)
            s.flush()
        return waiting_state(s, series, NOW)


def season(series):
    return next(x for x in series.seasons if x.number == 2)


def announce(s, series, kind="season_announced", **payload):
    s.add(
        m.Event(
            type=kind,
            fingerprint=f"{kind}{payload}",
            series_id=series.id,
            payload_json=json.dumps(payload),
        )
    )


def test_airing(db):
    assert state(db) == {"key": "airing", "season": 2, "have": 2, "expected": 4}


def test_missing_files_win_over_airing(db):
    def drop(s, series):
        season(series).episodes[1].has_file = False

    assert state(db, drop)["key"] == "missing"
    assert state(db, drop)["missing"] == 1


def test_disputed_and_unknown_count(db):
    def disputed(s, series):
        season(series).disputed, season(series).anilist_count = True, 6

    assert state(db, disputed) == {
        "key": "disputed",
        "season": 2,
        "have": 2,
        "expected": 4,
        "anilist": 6,
    }

    def unknown(s, series):
        season(series).expected_count = None

    assert state(db, unknown)["key"] == "count_unknown"


def test_announcements_after_a_complete_season(db):
    def complete(s, series):
        season(series).state = "complete"
        for e in season(series).episodes:
            e.has_file, e.air_date_utc = True, NOW - timedelta(days=30)

    assert state(db, complete) == {"key": "complete_no_sequel", "season": 2}

    def ended(s, series):
        complete(s, series)
        series.status = "ended"

    assert state(db, ended)["key"] == "ended"

    def renewed(s, series):
        complete(s, series)
        announce(s, series, season=2, first_air=None)  # the current season: ignored
        announce(s, series, season=3, first_air=None)

    assert state(db, renewed) == {
        "key": "renewed_open",
        "season": 3,
        "sequel_title": None,
        "first_air": None,
    }

    def sequel(s, series):
        complete(s, series)
        announce(s, series, "sequel_announced", sequel_title="Slime Movie", first_air="2020-01-01")
        announce(s, series, "sequel_announced", sequel_title="Slime 3", first_air="2027-04-01")

    assert state(db, sequel)["sequel_title"] == "Slime 3"
    assert state(db, sequel)["key"] == "announced"


def test_not_followed_and_nothing_known(db):
    def unfollow(s, series):
        series.followed = False

    assert state(db, unfollow) == {"key": "not_followed"}

    def empty(s, series):
        for x in list(series.seasons):
            series.seasons.remove(x)

    assert state(db, empty) == {"key": "nothing_known"}


def test_scheduled_season_names_its_start_or_falls_back_to_the_announcement(db):
    def scheduled(s, series):
        x = season(series)
        x.state = "scheduled"
        for e in x.episodes:
            e.has_file, e.air_date_utc = False, NOW + timedelta(days=10 + e.number)

    result = state(db, scheduled)
    assert result["key"] == "scheduled"
    assert result["first_air"][:10] == (NOW + timedelta(days=11)).date().isoformat()

    def undated(s, series):
        scheduled(s, series)
        for e in season(series).episodes:
            e.air_date_utc = None

    assert state(db, undated) == {"key": "renewed_open", "season": 2}

    def with_sequel(s, series):
        undated(s, series)
        announce(
            s, series, "sequel_announced", sequel_title="Slime 2nd Season", first_air="2027-01-01"
        )

    assert state(db, with_sequel)["key"] == "announced"

    def with_season(s, series):
        undated(s, series)
        announce(s, series, season=2, first_air="2027-04-05")

    assert state(db, with_season)["first_air"] == "2027-04-05"
