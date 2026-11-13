import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from finalarr.crypto import SecretBox
from finalarr.db import models as m
from finalarr.db.session import Database
from finalarr.services.reconciler import Reconciler

from ..fakes import FakeSonarr, make_episodes, make_series

NOW = datetime(2026, 4, 1, tzinfo=UTC)


@pytest.fixture
def env(tmp_path):
    from cryptography.fernet import Fernet

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
    clock = {"now": NOW}
    reconciler = Reconciler(db, box, client_factory=lambda _i: sonarr, clock=lambda: clock["now"])
    yield db, sonarr, reconciler, clock
    db.dispose()


def follow(db, sonarr_id):
    with db.session() as s:
        s.scalar(select(m.Series).where(m.Series.sonarr_id == sonarr_id)).followed = True
        s.commit()


def events(db):
    with db.session() as s:
        return [
            (e.type, json.loads(e.payload_json))
            for e in s.scalars(select(m.Event).order_by(m.Event.id))
        ]


def test_full_sync_stores_series_without_fetching_episodes_of_unfollowed(env):
    db, sonarr, reconciler, _ = env
    sonarr.add(
        make_series(1, "Slime", seasons=(0, 1, 2), series_type="anime"),
        make_episodes(1, 1, 3, set()),
    )
    sonarr.add(make_series(2, "Severance"))
    reconciler.reconcile(1)
    with db.session() as s:
        rows = s.scalars(select(m.Series).order_by(m.Series.sonarr_id)).all()
        assert [(r.title, r.series_type, r.poster_url) for r in rows] == [
            ("Slime", "anime", "https://img/1.jpg"),
            ("Severance", "standard", "https://img/2.jpg"),
        ]
        assert [season.number for season in rows[0].seasons] == [0, 1, 2]
    assert sonarr.calls == ["series_list"]


def test_followed_series_gets_episodes_and_a_silent_baseline(env):
    db, sonarr, reconciler, _ = env
    sonarr.add(make_series(1, "Slime"), make_episodes(1, 1, 3, {1, 2, 3}))
    reconciler.reconcile(1)
    follow(db, 1)
    reconciler.reconcile(1)
    with db.session() as s:
        season = s.scalar(select(m.Season).where(m.Season.number == 1))
        assert [e.number for e in season.episodes] == [1, 2, 3]
        assert season.state == "complete"
        assert season.expected_count == 3
        assert json.loads(season.memory_json)["initialized"] is True
    assert events(db) == []


def test_new_file_creates_one_event_and_reruns_add_nothing(env):
    db, sonarr, reconciler, clock = env
    sonarr.add(make_series(1, "Slime"), make_episodes(1, 1, 4, {1}))
    reconciler.reconcile(1)
    follow(db, 1)
    reconciler.reconcile(1)
    sonarr.episodes_by_series[1] = make_episodes(1, 1, 4, {1, 2, 3})
    clock["now"] += timedelta(minutes=30)
    reconciler.reconcile(1)
    reconciler.reconcile(1)
    assert [(t, p["episodes"]) for t, p in events(db)] == [("episodes_available", [2, 3])]


def test_event_rows_link_instance_series_and_season(env):
    db, sonarr, reconciler, _ = env
    sonarr.add(make_series(1, "Slime"), make_episodes(1, 1, 2, set()))
    reconciler.reconcile(1)
    follow(db, 1)
    reconciler.reconcile(1)
    sonarr.episodes_by_series[1] = make_episodes(1, 1, 2, {1})
    reconciler.reconcile(1)
    with db.session() as s:
        event = s.scalar(select(m.Event))
        assert (event.instance_id, event.series_id) == (1, 1)
        assert event.season_id is not None
        assert json.loads(event.payload_json)["title"] == "Slime"


def test_single_series_reconcile_only_touches_that_series(env):
    db, sonarr, reconciler, _ = env
    sonarr.add(make_series(1, "Slime"), make_episodes(1, 1, 2, set()))
    sonarr.add(make_series(2, "Severance"), make_episodes(2, 1, 2, set()))
    reconciler.reconcile(1)
    follow(db, 1)
    follow(db, 2)
    sonarr.calls.clear()
    reconciler.reconcile(1, sonarr_series_id=2)
    assert sonarr.calls == ["series:2", "episodes:2"]


def test_single_series_reconcile_adds_a_series_sonarr_just_created(env):
    db, sonarr, reconciler, _ = env
    sonarr.add(make_series(7, "New Show"))
    reconciler.reconcile(1, sonarr_series_id=7)
    with db.session() as s:
        assert s.scalar(select(m.Series.title)) == "New Show"


def test_series_and_episodes_removed_in_sonarr_are_removed(env):
    db, sonarr, reconciler, _ = env
    sonarr.add(make_series(1, "Slime"), make_episodes(1, 1, 3, set()))
    sonarr.add(make_series(2, "Gone"))
    reconciler.reconcile(1)
    follow(db, 1)
    reconciler.reconcile(1)
    del sonarr.series_by_id[2]
    sonarr.episodes_by_series[1] = make_episodes(1, 1, 2, set())
    reconciler.reconcile(1)
    with db.session() as s:
        assert s.scalars(select(m.Series.title)).all() == ["Slime"]
        assert s.scalars(select(m.Episode.number).order_by(m.Episode.number)).all() == [1, 2]


def test_sonarr_down_records_the_error_and_success_clears_it(env):
    db, sonarr, reconciler, _ = env
    sonarr.down = True
    reconciler.reconcile(1)
    with db.session() as s:
        instance = s.get(m.SonarrInstance, 1)
        assert instance.last_error == "Sonarr cannot be reached"
        assert instance.last_sync_at is None
    sonarr.down = False
    reconciler.reconcile(1)
    with db.session() as s:
        instance = s.get(m.SonarrInstance, 1)
        assert instance.last_error is None
        assert instance.last_sync_at is not None


def test_disabled_or_missing_instances_are_skipped(env):
    db, sonarr, reconciler, _ = env
    with db.session() as s:
        s.get(m.SonarrInstance, 1).enabled = False
        s.commit()
    reconciler.reconcile(1)
    reconciler.reconcile(99)
    assert sonarr.calls == []


def test_unfollowing_keeps_state_but_stops_fetching(env):
    db, sonarr, reconciler, _ = env
    sonarr.add(make_series(1, "Slime"), make_episodes(1, 1, 2, set()))
    reconciler.reconcile(1)
    follow(db, 1)
    reconciler.reconcile(1)
    with db.session() as s:
        s.scalar(select(m.Series)).followed = False
        s.commit()
    sonarr.calls.clear()
    reconciler.reconcile(1)
    assert sonarr.calls == ["series_list"]


def test_policy_comes_from_settings(env):
    db, sonarr, reconciler, clock = env
    from finalarr.services.settings_store import save_settings

    with db.session() as s:
        save_settings(s, {"renotify_after_file_loss": True})
        s.commit()
    sonarr.add(make_series(1, "Slime"), make_episodes(1, 1, 2, set()))
    reconciler.reconcile(1)
    follow(db, 1)
    reconciler.reconcile(1)
    for files in ({1}, set(), {1}):
        sonarr.episodes_by_series[1] = make_episodes(1, 1, 2, files)
        clock["now"] += timedelta(minutes=30)
        reconciler.reconcile(1)
    assert [t for t, _ in events(db)] == ["episodes_available", "episodes_available"]
