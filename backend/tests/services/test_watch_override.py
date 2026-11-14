from datetime import UTC, date, datetime

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from finalarr.crypto import SecretBox
from finalarr.db import models as m
from finalarr.db.session import Database
from finalarr.services.watch_state import correct_watched, series_watch
from finalarr.services.watch_sync import WatchSync
from finalarr.sources.media import MediaUserInfo, WatchedItem

NOW = datetime(2026, 11, 14, 12, tzinfo=UTC)


class Client:
    def __init__(self, items):
        self.items = items

    def users(self):
        return [MediaUserInfo("u1", "Dennis")]

    def watched(self, user_id):
        return self.items


@pytest.fixture
def env(tmp_path):
    db = Database(tmp_path / "f.db")
    db.migrate()
    box = SecretBox(Fernet.generate_key().decode())
    with db.session() as s:
        instance = m.SonarrInstance(name="H", url="http://s", api_key_enc="x", webhook_token="t")
        series = m.Series(instance=instance, sonarr_id=1, tvdb_id=100, title="Slime", followed=True)
        season = m.Season(number=1)
        season.episodes += [
            m.Episode(sonarr_episode_id=n, number=n, has_file=True) for n in (1, 2, 3)
        ]
        series.seasons.append(season)
        server = m.MediaServer(kind="emby", name="Emby", url="http://e", token_enc=box.encrypt("k"))
        server.users = [m.MediaUser(remote_id="u1", name="Dennis", selected=True, baseline_at=NOW)]
        s.add_all([series, server])
        s.commit()
    yield db, box
    db.dispose()


def sync(env, items):
    db, box = env
    WatchSync(db, box, client_factory=lambda server: Client(items), clock=lambda: NOW).run()


def state(db):
    with db.session() as s:
        return series_watch(s, s.scalar(select(m.Series)))


def correct(db, episodes, watched):
    with db.session() as s:
        correct_watched(s, 1, 1, episodes, watched, today=NOW.date())
        s.commit()


def test_corrections_apply_at_once_and_survive_syncs(env):
    db, _ = env
    sync(env, [WatchedItem(100, "Slime", 1, 1, None), WatchedItem(100, "Slime", 1, 2, None)])
    correct(db, [(1, 2)], False)  # the server is wrong about E02
    correct(db, [(1, 3)], True)  # watched elsewhere
    after = state(db)
    assert sorted(after["episodes"]) == ["1x1", "1x3"]
    assert sorted(after["corrected"]) == ["1x2", "1x3"]
    sync(env, [WatchedItem(100, "Slime", 1, 1, None), WatchedItem(100, "Slime", 1, 2, None)])
    assert sorted(state(db)["episodes"]) == ["1x1", "1x3"]


def test_a_watched_correction_ends_once_the_server_agrees(env):
    db, _ = env
    correct(db, [(1, 3)], True)
    sync(env, [WatchedItem(100, "Slime", 1, 3, date(2026, 11, 13))])
    assert state(db)["corrected"] == []
    with db.session() as s:
        assert s.scalar(select(m.WatchedEpisode.watched_on)) == date(2026, 11, 13)


def test_taking_a_correction_back_lets_the_server_decide_again(env):
    db, _ = env
    sync(env, [WatchedItem(100, "Slime", 1, 2, None)])
    correct(db, [(1, 2)], False)
    correct(db, [(1, 2)], None)
    assert state(db)["corrected"] == []
    sync(env, [WatchedItem(100, "Slime", 1, 2, None)])
    assert sorted(state(db)["episodes"]) == ["1x2"]


def test_viewers_and_episode_ids(env):
    db, _ = env
    correct(db, [(1, 1), (1, 2)], True)
    watch = state(db)
    assert watch["viewers"] == [{"id": 1, "name": "Dennis", "server": "Emby"}]
    assert watch["episodes"] == {"1x1": [1], "1x2": [1]}
