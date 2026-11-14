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
    assert sonarr.calls == ["tags", "series_list"]


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
        assert json.loads(event.payload_json)["sonarr_url"] == "http://s:1/series/slime"


def test_single_series_reconcile_only_touches_that_series(env):
    db, sonarr, reconciler, _ = env
    sonarr.add(make_series(1, "Slime"), make_episodes(1, 1, 2, set()))
    sonarr.add(make_series(2, "Severance"), make_episodes(2, 1, 2, set()))
    reconciler.reconcile(1)
    follow(db, 1)
    follow(db, 2)
    sonarr.calls.clear()
    reconciler.reconcile(1, sonarr_series_id=2)
    assert sonarr.calls == ["tags", "series:2", "episodes:2"]


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
    assert sonarr.calls == ["tags", "series_list"]


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


def test_a_season_new_to_a_known_series_is_announced(env):
    """The silent baseline is per series: a later season must not be swallowed."""
    db, sonarr, reconciler, clock = env
    sonarr.add(make_series(1, "Slime", seasons=(1,)), make_episodes(1, 1, 2, {1, 2}))
    reconciler.reconcile(1)
    follow(db, 1)
    reconciler.reconcile(1)
    future = [
        e.model_copy(update={"air_date_utc": NOW + timedelta(days=60)})
        for e in make_episodes(1, 2, 12, set())
    ]
    sonarr.add(make_series(1, "Slime", seasons=(1, 2)), make_episodes(1, 1, 2, {1, 2}) + future)
    clock["now"] += timedelta(minutes=30)
    reconciler.reconcile(1)
    assert [(t, p["season"], p["expected"]) for t, p in events(db)] == [("season_announced", 2, 12)]


def test_newly_followed_series_still_starts_silently(env):
    db, sonarr, reconciler, _ = env
    sonarr.add(
        make_series(1, "Slime", seasons=(1, 2)),
        make_episodes(1, 1, 2, {1}) + make_episodes(1, 2, 2, set()),
    )
    reconciler.reconcile(1)
    follow(db, 1)
    reconciler.reconcile(1)
    assert events(db) == []


def test_parts_flow_into_the_evaluator_and_the_payload(env):
    db, sonarr, reconciler, clock = env
    sonarr.add(
        make_series(1, "Mushoku", seasons=(2,), series_type="anime"), make_episodes(1, 2, 4, {1})
    )
    reconciler.reconcile(1)
    follow(db, 1)
    with db.session() as s:
        season = s.scalar(select(m.Season))
        season.anilist_count = 4
        season.parts_mode = "parts"
        season.parts += [
            m.AnimePart(
                part_index=1, anilist_id=146065, episode_from=1, episode_to=2, title="Mushoku II"
            ),
            m.AnimePart(
                part_index=2,
                anilist_id=166873,
                episode_from=3,
                episode_to=4,
                title="Mushoku II Part 2",
            ),
        ]
        s.commit()
    reconciler.reconcile(1)
    sonarr.episodes_by_series[1] = make_episodes(1, 2, 4, {1, 2})
    clock["now"] += timedelta(minutes=30)
    reconciler.reconcile(1)
    [(kind, payload)] = events(db)
    assert kind == "part_complete"
    assert (payload["part"], payload["part_title"], payload["parts_mode"]) == (
        1,
        "Mushoku II",
        "parts",
    )


def test_tag_labels_are_stored(env):
    db, sonarr, reconciler, _ = env
    sonarr.tag_labels = {1: "anime", 2: "kids"}
    sonarr.add(make_series(1, "Slime", tags=(1, 2)))
    sonarr.add(make_series(2, "Andor"))
    reconciler.reconcile(1)
    with db.session() as s:
        tags = {r.title: json.loads(r.tags_json) for r in s.scalars(select(m.Series))}
    assert tags == {"Slime": ["anime", "kids"], "Andor": []}


def test_sonarr_replacing_an_episode_id_keeps_the_number(env):
    db, sonarr, reconciler, _ = env
    sonarr.add(make_series(1, "Slime"), make_episodes(1, 1, 2, {1}))
    reconciler.reconcile(1)
    follow(db, 1)
    reconciler.reconcile(1)
    replaced = [
        e.model_copy(update={"id": e.id + 500}) if e.episode_number == 2 else e
        for e in make_episodes(1, 1, 2, {1})
    ]
    sonarr.episodes_by_series[1] = replaced
    reconciler.reconcile(1)
    with db.session() as s:
        assert s.get(m.SonarrInstance, 1).last_error is None
        ids = sorted(s.scalars(select(m.Episode.sonarr_episode_id)))
    assert ids == [1101, 1602]


def test_series_details_from_sonarr_are_stored(env):
    db, sonarr, reconciler, _ = env
    series = make_series(1, "Slime").model_copy(
        update={
            "overview": "A slime story.",
            "network": "Tokyo MX",
            "runtime": 24,
            "genres": ("Anime", "Fantasy"),
        }
    )
    sonarr.add(series)
    reconciler.reconcile(1)
    with db.session() as s:
        row = s.scalar(select(m.Series))
        assert (row.overview, row.network, row.runtime, json.loads(row.genres_json)) == (
            "A slime story.",
            "Tokyo MX",
            24,
            ["Anime", "Fantasy"],
        )


def _watched(env, episodes):
    db, sonarr, reconciler, clock = env
    sonarr.add(make_series(1, "Slime"), episodes)
    reconciler.reconcile(1)
    follow(db, 1)
    reconciler.reconcile(1)
    return db, sonarr, reconciler, clock


def test_a_moved_air_date_is_reported_as_a_delay(env):
    future = [
        e.model_copy(update={"air_date_utc": NOW + timedelta(days=7 * e.episode_number)})
        for e in make_episodes(1, 1, 3, set())
    ]
    db, sonarr, reconciler, _clock = _watched(env, future)
    moved = [
        e.model_copy(update={"air_date_utc": e.air_date_utc + timedelta(days=14)})
        if e.episode_number == 2
        else e
        for e in future
    ]
    sonarr.episodes_by_series[1] = moved
    reconciler.reconcile(1)
    reconciler.reconcile(1)
    delays = [(t, p) for t, p in events(db) if t == "episode_delayed"]
    assert len(delays) == 1
    payload = delays[0][1]
    assert (payload["season"], payload["episode"]) == (1, 2)
    assert payload["old"][:10] == (NOW + timedelta(days=14)).date().isoformat()
    assert payload["new"][:10] == (NOW + timedelta(days=28)).date().isoformat()
    with db.session() as s:
        row = s.scalar(select(m.Episode).where(m.Episode.number == 2))
        assert row.delayed_from is not None


def test_small_shifts_downloaded_episodes_and_unwatched_series_are_not_delays(env):
    future = [
        e.model_copy(update={"air_date_utc": NOW + timedelta(days=7 * e.episode_number)})
        for e in make_episodes(1, 1, 2, set())
    ]
    db, sonarr, reconciler, _clock = _watched(env, future)
    shifted = [
        e.model_copy(update={"air_date_utc": e.air_date_utc + timedelta(hours=2)}) for e in future
    ]
    sonarr.episodes_by_series[1] = shifted
    reconciler.reconcile(1)
    assert [t for t, _ in events(db) if t == "episode_delayed"] == []


def test_a_removed_date_is_a_delay_to_unknown(env):
    future = [
        e.model_copy(update={"air_date_utc": NOW + timedelta(days=7)})
        for e in make_episodes(1, 1, 1, set())
    ]
    db, sonarr, reconciler, _clock = _watched(env, future)
    sonarr.episodes_by_series[1] = [future[0].model_copy(update={"air_date_utc": None})]
    reconciler.reconcile(1)
    [(_kind, payload)] = [(t, p) for t, p in events(db) if t == "episode_delayed"]
    assert payload["new"] is None
