import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError

from finalarr.db import models as m
from finalarr.db.session import Database

TABLES = {
    "sonarr_instances",
    "series",
    "seasons",
    "episodes",
    "anime_parts",
    "events",
    "channels",
    "deliveries",
    "settings",
    "reconcile_requests",
    "anilist_mappings",
    "anilist_cache",
}


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "finalarr.db")
    database.migrate()
    yield database
    database.dispose()


def _series(session):
    instance = m.SonarrInstance(
        name="Home", url="http://sonarr:8989", api_key_enc="x", webhook_token="t" * 64
    )
    series = m.Series(instance=instance, sonarr_id=1, title="Slime", series_type="anime")
    season = m.Season(series=series, number=3)
    m.Episode(season=season, sonarr_episode_id=11, number=1)
    session.add(instance)
    session.flush()
    return instance, series, season


def test_migration_creates_every_table(db):
    assert set(inspect(db.engine).get_table_names()) >= TABLES


def test_downgrade_removes_everything(db):
    db.downgrade("base")
    assert set(inspect(db.engine).get_table_names()) <= {"alembic_version"}


def test_models_and_migrations_agree(db):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    with db.engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), m.Base.metadata)
    assert diff == []


def test_connection_pragmas(db):
    with db.engine.connect() as c:
        assert c.execute(text("PRAGMA foreign_keys")).scalar() == 1
        assert c.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert c.execute(text("PRAGMA busy_timeout")).scalar() == 5000
        assert c.execute(text("PRAGMA synchronous")).scalar() == 2


def test_fingerprint_is_unique(db):
    with db.session() as s:
        s.add(m.Event(type="season_complete", fingerprint="f", payload_json="{}"))
        s.flush()
        s.add(m.Event(type="season_complete", fingerprint="f", payload_json="{}"))
        with pytest.raises(IntegrityError):
            s.flush()


def test_deleting_a_series_cascades_but_keeps_event_history(db):
    with db.session() as s:
        instance, series, season = _series(s)
        s.add(
            m.Event(
                type="episodes_available",
                fingerprint="e",
                payload_json="{}",
                instance_id=instance.id,
                series_id=series.id,
                season_id=season.id,
            )
        )
        s.commit()
        s.delete(series)
        s.commit()
        assert s.scalar(select(m.Episode)) is None
        event = s.scalar(select(m.Event))
        assert event is not None
        assert (event.series_id, event.season_id) == (None, None)


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE seasons SET state = 'bogus'",
        "UPDATE seasons SET parts_mode = 'bogus'",
        "UPDATE series SET series_type = 'bogus'",
        "UPDATE episodes SET number = -1",
    ],
)
def test_check_constraints(db, statement):
    with db.session() as s:
        _series(s)
        s.commit()
        with pytest.raises(IntegrityError):
            s.execute(text(statement))


def test_anime_part_range_is_checked(db):
    with db.session() as s:
        _, _, season = _series(s)
        s.add(m.AnimePart(season=season, anilist_id=1, part_index=1, episode_from=5, episode_to=2))
        with pytest.raises(IntegrityError):
            s.flush()


def test_one_delivery_per_event_and_channel(db):
    with db.session() as s:
        event = m.Event(type="season_complete", fingerprint="f", payload_json="{}")
        channel = m.Channel(name="TG", kind="telegram", apprise_url_enc="x")
        s.add_all([event, channel, m.Delivery(event=event, channel=channel)])
        s.flush()
        s.add(m.Delivery(event=event, channel=channel))
        with pytest.raises(IntegrityError):
            s.flush()


def test_migrate_is_idempotent(db):
    db.migrate()
    assert set(inspect(db.engine).get_table_names()) >= TABLES


def test_ping_reports_a_broken_connection(db, monkeypatch):
    assert db.ping()

    def broken():
        raise OSError("disk gone")

    monkeypatch.setattr(db.engine, "connect", broken)
    assert not db.ping()


def test_sequel_announced_is_an_allowed_event_type(db):
    with db.session() as s:
        s.add(m.Event(type="sequel_announced", fingerprint="seq", payload_json="{}"))
        s.flush()
        s.add(m.Event(type="nonsense", fingerprint="bad", payload_json="{}"))
        with pytest.raises(IntegrityError):
            s.flush()
