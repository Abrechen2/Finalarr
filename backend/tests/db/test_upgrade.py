"""Upgrades keep data: SQLite batch migrations rebuild tables, and with foreign keys on, a
dropped parent table would cascade into its children."""

from alembic import command
from sqlalchemy import text

from finalarr.db.session import Database

OLDEST = [
    "INSERT INTO sonarr_instances (id, name, url, api_key_enc, webhook_token, enabled,"
    " created_at) VALUES (1, 'H', 'http://s', 'x', 't', 1, '2026-01-01')",
    "INSERT INTO series (id, instance_id, sonarr_id, title, sort_title, title_slug,"
    " series_type, status, monitored, followed, include_specials, respect_monitoring,"
    " anilist_resolution, updated_at) VALUES (1, 1, 1, 'Slime', 'slime', 'slime', 'anime',"
    " 'continuing', 1, 1, 0, 1, 'none', '2026-01-01')",
    "INSERT INTO seasons (id, series_id, number, monitored, disputed, parts_mode, state,"
    " state_since) VALUES (1, 1, 1, 1, 0, 'season', 'airing', '2026-01-01')",
    "INSERT INTO episodes (id, season_id, sonarr_episode_id, number, title, monitored,"
    " has_file) VALUES (1, 1, 1, 1, 'One', 1, 1)",
    "INSERT INTO channels (id, name, kind, apprise_url_enc, enabled, language,"
    " event_filter_json, created_at) VALUES (1, 'T', 'telegram', 'x', 1, 'de', '[]', '2026-01-01')",
    "INSERT INTO events (id, type, instance_id, series_id, season_id, fingerprint,"
    " payload_json, created_at) VALUES (1, 'finale_available', 1, 1, 1, 'f', '{}', '2026-01-01')",
    "INSERT INTO deliveries (id, event_id, channel_id, status, attempts, next_attempt_at,"
    " sent_at) VALUES (1, 1, 1, 'sent', 1, '2026-01-01', '2026-01-01')",
    "INSERT INTO settings (key, value_json) VALUES ('language', '\"de\"')",
]
MEDIA = [
    "INSERT INTO media_servers (id, kind, name, url, token_enc, enabled, created_at)"
    " VALUES (1, 'emby', 'Emby', 'http://e', 'x', 1, '2026-01-01')",
    "INSERT INTO media_users (id, server_id, remote_id, name, selected)"
    " VALUES (1, 1, 'u', 'Dennis', 1)",
    "INSERT INTO watched_episodes (user_id, series_id, season_number, episode_number)"
    " VALUES (1, 1, 1, 1)",
]
TABLES = [
    "sonarr_instances",
    "series",
    "seasons",
    "episodes",
    "channels",
    "events",
    "deliveries",
    "settings",
    "media_servers",
    "media_users",
    "watched_episodes",
]


def _run(db, statements):
    with db.engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def _counts(db):
    with db.engine.connect() as connection:
        return {
            t: connection.execute(text(f"SELECT count(*) FROM {t}")).scalar()  # noqa: S608
            for t in TABLES
        }


def test_upgrading_from_the_first_schema_keeps_every_row(tmp_path):
    db = Database(tmp_path / "finalarr.db")
    command.upgrade(db._alembic(), "0001")
    _run(db, OLDEST)
    command.upgrade(db._alembic(), "0010")
    _run(db, MEDIA)
    db.migrate()
    assert _counts(db) == dict.fromkeys(TABLES, 1)
    db.dispose()


def test_a_pending_migration_backs_the_database_up_first(tmp_path):
    db = Database(tmp_path / "finalarr.db")
    command.upgrade(db._alembic(), "0012")
    _run(db, OLDEST)
    db.migrate()
    backups = list((tmp_path / "backups").glob("finalarr-before-*.db"))
    assert [b.name.startswith("finalarr-before-0013-") for b in backups] == [True]
    copy = Database(backups[0])
    assert _counts(copy)["deliveries"] == 1
    copy.dispose()
    db.migrate()  # nothing pending: no second backup
    assert len(list((tmp_path / "backups").iterdir())) == 1
    db.dispose()


def test_a_new_database_needs_no_backup(tmp_path):
    db = Database(tmp_path / "finalarr.db")
    db.migrate()
    assert not (tmp_path / "backups").exists()
    db.dispose()


def test_only_the_newest_pre_migration_backups_are_kept(tmp_path):
    folder = tmp_path / "backups"
    folder.mkdir()
    for i in range(7):
        (folder / f"finalarr-before-0012-2026010{i}-000000.db").write_bytes(b"")
    (folder / "finalarr-20260101-000000.db").write_bytes(b"")  # a manual backup stays
    db = Database(tmp_path / "finalarr.db")
    command.upgrade(db._alembic(), "0012")
    db.migrate()
    names = sorted(p.name for p in folder.iterdir())
    assert len([n for n in names if n.startswith("finalarr-before-")]) == 5
    assert "finalarr-20260101-000000.db" in names
    assert any(n.startswith("finalarr-before-0013-") for n in names)
    db.dispose()
