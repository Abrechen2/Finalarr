import json
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select

from finalarr.db import models as m
from finalarr.db.session import Database
from finalarr.services.announcements import Announced, AnnouncementWatcher, SourceError
from finalarr.services.reconciler import Reconciler

from ..fakes import FakeSonarr, make_episodes, make_series

NOW = datetime(2026, 11, 13, 12, tzinfo=UTC)


class FakeSource:
    def __init__(self, name, seasons, error=None):
        self.name = name
        self._seasons = seasons
        self.error = error
        self.calls = []

    def seasons(self, tvdb_id):
        self.calls.append(tvdb_id)
        if self.error:
            raise self.error
        return self._seasons.get(tvdb_id, [])


@pytest.fixture
def env(tmp_path):
    from cryptography.fernet import Fernet

    from finalarr.crypto import SecretBox

    db = Database(tmp_path / "f.db")
    db.migrate()
    box = SecretBox(Fernet.generate_key().decode())
    with db.session() as s:
        s.add(
            m.SonarrInstance(
                name="C", url="http://s:1", api_key_enc=box.encrypt("k"), webhook_token="t"
            )
        )
        s.commit()
    sonarr = FakeSonarr()
    sonarr.add(
        make_series(7, "Severance", seasons=(1, 2)),
        make_episodes(7, 1, 2, {1, 2}) + make_episodes(7, 2, 2, {1, 2}),
    )
    reconciler = Reconciler(db, box, client_factory=lambda _i: sonarr, clock=lambda: NOW)
    reconciler.reconcile(1)
    with db.session() as s:
        s.scalar(select(m.Series)).followed = True
        s.commit()
    reconciler.reconcile(1)
    yield db, sonarr, reconciler
    db.dispose()


TVDB = 1007  # make_series uses 1000 + id


def watch(db, *sources, now=NOW):
    created = []
    AnnouncementWatcher(
        db, list(sources), on_events=lambda s, ev: created.extend(ev), clock=lambda: now
    ).run()
    return created


def events(db):
    with db.session() as s:
        return [
            (e.type, json.loads(e.payload_json))
            for e in s.scalars(select(m.Event).order_by(m.Event.id))
        ]


def test_new_season_is_announced_once_with_merged_details(env):
    db, *_ = env
    tvmaze = FakeSource("tvmaze", {TVDB: [Announced(3, None, None)]})
    tmdb = FakeSource(
        "tmdb", {TVDB: [Announced(3, date(2027, 3, 5), 10), Announced(2, date(2025, 1, 17), 10)]}
    )
    created = watch(db, tvmaze, tmdb)
    assert len(created) == 1
    [(kind, payload)] = events(db)
    assert kind == "season_announced"
    assert (payload["season"], payload["first_air"], payload["expected"]) == (3, "2027-03-05", 10)
    assert payload["sources"] == ["tmdb", "tvmaze"]
    assert watch(db, tvmaze, tmdb) == []


def test_sonarr_listing_the_season_later_does_not_announce_twice(env):
    db, sonarr, reconciler = env
    watch(db, FakeSource("tvmaze", {TVDB: [Announced(3, date(2027, 3, 5), 10)]}))
    future = [
        e.model_copy(update={"air_date_utc": NOW + timedelta(days=100)})
        for e in make_episodes(7, 3, 10, set())
    ]
    sonarr.add(
        make_series(7, "Severance", seasons=(1, 2, 3)),
        make_episodes(7, 1, 2, {1, 2}) + make_episodes(7, 2, 2, {1, 2}) + future,
    )
    reconciler.reconcile(1)
    assert [k for k, _ in events(db)] == ["season_announced"]


def test_seasons_sonarr_already_lists_or_old_ones_are_skipped(env):
    db, *_ = env
    source = FakeSource(
        "tmdb",
        {
            TVDB: [
                Announced(2, date(2027, 1, 1), 10),
                Announced(0, None, None),
                Announced(5, date(2020, 1, 1), 8),
            ]
        },
    )
    assert watch(db, source) == []


def test_a_failing_source_does_not_stop_the_others(env):
    db, *_ = env
    broken = FakeSource("trakt", {}, error=SourceError("down"))
    working = FakeSource("tvmaze", {TVDB: [Announced(3, None, None)]})
    assert len(watch(db, broken, working)) == 1


def test_anime_with_a_fribb_mapping_is_left_to_anilist(env):
    db, *_ = env
    with db.session() as s:
        s.add(m.AnilistMapping(tvdb_id=TVDB, tvdb_season=1, anilist_id=5, source="fribb"))
        s.commit()
    source = FakeSource("tvmaze", {TVDB: [Announced(3, None, None)]})
    assert watch(db, source) == []
    assert source.calls == []


def test_switched_off_sources_are_not_asked(env):
    from finalarr.services.source_catalog import set_source

    db, *_ = env
    with db.session() as s:
        set_source(s, "tvmaze", False)
        s.commit()
    tvmaze = FakeSource("tvmaze", {TVDB: [Announced(3, None, None)]})
    assert watch(db, tvmaze) == []


def test_listed_seasons_get_the_largest_external_episode_count(env):
    # Forgejo #22: TVDB often lists only part of a live-action season; the count from
    # TVmaze/TMDB lets "complete" wait for the rest.
    db, *_ = env
    tvmaze = FakeSource("tvmaze", {TVDB: [Announced(2, date(2025, 1, 17), 8)]})
    tmdb = FakeSource("tmdb", {TVDB: [Announced(2, date(2025, 1, 17), 10)]})
    watch(db, tvmaze, tmdb)
    with db.session() as s:
        season = s.scalar(select(m.Season).where(m.Season.number == 2))
        assert (season.external_count, season.external_source) == (10, "tmdb")
