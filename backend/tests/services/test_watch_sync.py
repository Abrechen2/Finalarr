from datetime import UTC, date, datetime

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from finalarr.crypto import SecretBox
from finalarr.db import models as m
from finalarr.db.session import Database
from finalarr.services.reconcile_queue import take_all
from finalarr.services.settings_store import save_settings
from finalarr.services.watch_sync import WatchSync
from finalarr.sources.media import MediaError, MediaUserInfo, WatchedItem

NOW = datetime(2026, 11, 14, 12, tzinfo=UTC)
RECENT = date(2026, 11, 10)
OLD = date(2026, 8, 1)


class FakeClient:
    def __init__(self, users, watched, fail=False):
        self._users, self._watched, self.fail, self.asked = users, watched, fail, []

    def test(self):
        return "Fake 1.0"

    def users(self):
        if self.fail:
            raise MediaError("Emby cannot be reached")
        return self._users

    def watched(self, user_id):
        self.asked.append(user_id)
        return self._watched.get(user_id, [])


def w(tvdb, season, episode, on=RECENT, title="Show"):
    return WatchedItem(tvdb, title, season, episode, on)


@pytest.fixture
def env(tmp_path):
    db = Database(tmp_path / "f.db")
    db.migrate()
    box = SecretBox(Fernet.generate_key().decode())
    with db.session() as s:
        instance = m.SonarrInstance(
            name="Home", url="http://s:1", api_key_enc="x", webhook_token="t"
        )
        s.add_all(
            [
                m.Series(instance=instance, sonarr_id=1, tvdb_id=100, title="Slime"),
                m.Series(instance=instance, sonarr_id=2, tvdb_id=200, title="Andor"),
                m.Series(
                    instance=instance, sonarr_id=3, tvdb_id=300, title="Old", follow_mode="never"
                ),
                m.Series(
                    instance=instance,
                    sonarr_id=4,
                    tvdb_id=400,
                    title="Kept",
                    followed=True,
                    follow_mode="always",
                ),
            ]
        )
        server = m.MediaServer(
            kind="emby", name="Emby", url="http://emby", token_enc=box.encrypt("k")
        )
        server.users = [
            m.MediaUser(remote_id="u1", name="Dennis", selected=True),
            m.MediaUser(remote_id="u2", name="Anna", selected=False),
        ]
        s.add(server)
        s.commit()
    yield db, box
    db.dispose()


def run(env, client):
    db, box = env
    newly = []
    WatchSync(
        db,
        box,
        client_factory=lambda server: client,
        clock=lambda: NOW,
        on_follow=lambda s, series: newly.extend(x.title for x in series),
    ).run()
    return newly


def series(db, title):
    with db.session() as s:
        return s.scalar(select(m.Series).where(m.Series.title == title))


USERS = [MediaUserInfo("u1", "Dennis"), MediaUserInfo("u2", "Anna"), MediaUserInfo("u3", "Guest")]


def test_watched_series_are_followed_automatically(env):
    client = FakeClient(
        USERS,
        {
            "u1": [
                w(100, 1, 1),
                w(100, 1, 2),  # Slime: 2 recent → follow
                w(200, 1, 1),
                w(200, 0, 1),  # Andor: 1 regular + a special → no
                w(300, 1, 1),
                w(300, 1, 2),  # Old: never → stays unfollowed
                w(999, 1, 1, title="Not in Sonarr"),
                w(None, 1, 1, title="No TVDB"),
            ],
            "u2": [w(200, 1, 2), w(200, 1, 3)],  # Anna is not selected
        },
    )
    assert run(env, client) == ["Slime"]
    db, _ = env
    assert client.asked == ["u1"]
    assert series(db, "Slime").followed and series(db, "Slime").follow_mode == "auto"
    assert not series(db, "Andor").followed
    assert not series(db, "Old").followed
    with db.session() as s:
        assert take_all(s) == [(1, 1)]
        server = s.scalar(select(m.MediaServer))
        assert server.last_error is None and server.last_sync_at is not None
        assert server.unmatched_json == '["No TVDB", "Not in Sonarr"]'
        assert [u.name for u in server.users] == ["Dennis", "Anna", "Guest"]
        assert s.query(m.WatchedEpisode).count() == 6  # only Dennis, matched series only


def test_old_views_do_not_count_and_thresholds_are_settings(env):
    db, _ = env
    old = FakeClient(USERS, {"u1": [w(100, 1, 1, OLD), w(100, 1, 2, OLD)]})
    assert run(env, old) == []
    with db.session() as s:
        save_settings(s, {"auto_follow_days": 120, "auto_follow_min_episodes": 2})
        s.commit()
    assert run(env, old) == ["Slime"]


def test_auto_follow_can_be_switched_off(env):
    db, _ = env
    with db.session() as s:
        save_settings(s, {"auto_follow": False})
        s.commit()
    assert run(env, FakeClient(USERS, {"u1": [w(100, 1, 1), w(100, 1, 2)]})) == []
    with db.session() as s:
        assert s.query(m.WatchedEpisode).count() == 2  # watched state is still shown


def test_a_rescan_replaces_the_users_state_and_drops_unselected_users(env):
    db, _ = env
    run(env, FakeClient(USERS, {"u1": [w(100, 1, 1), w(100, 1, 2)]}))
    with db.session() as s:
        s.add(m.WatchedEpisode(user_id=2, series_id=2, season_number=1, episode_number=1))
        s.commit()
    run(env, FakeClient(USERS, {"u1": [w(100, 1, 3)]}))
    with db.session() as s:
        rows = s.execute(select(m.WatchedEpisode.user_id, m.WatchedEpisode.episode_number)).all()
    assert rows == [(1, 3)]


def test_a_failing_server_keeps_its_data_and_records_the_error(env):
    db, _ = env
    run(env, FakeClient(USERS, {"u1": [w(100, 1, 1)]}))
    run(env, FakeClient(USERS, {}, fail=True))
    with db.session() as s:
        assert s.scalar(select(m.MediaServer)).last_error == "Emby cannot be reached"
        assert s.query(m.WatchedEpisode).count() == 1


def test_users_gone_from_the_server_are_removed(env):
    db, _ = env
    run(env, FakeClient([MediaUserInfo("u1", "Dennis")], {"u1": []}))
    with db.session() as s:
        assert [u.remote_id for u in s.scalars(select(m.MediaUser))] == ["u1"]
