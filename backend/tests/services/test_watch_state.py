from datetime import date

import pytest
from sqlalchemy import select

from finalarr.db import models as m
from finalarr.db.session import Database
from finalarr.services.watch_state import continue_watching, series_watch, watch_filter


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "f.db")
    database.migrate()
    with database.session() as s:
        instance = m.SonarrInstance(name="H", url="http://s", api_key_enc="x", webhook_token="t")
        slime = m.Series(
            instance=instance, sonarr_id=1, title="Slime", followed=True, poster_url="p"
        )
        season = m.Season(number=1)
        season.episodes += [
            m.Episode(sonarr_episode_id=i, number=i, has_file=i <= 3) for i in range(1, 5)
        ]
        slime.seasons.append(season)
        andor = m.Series(instance=instance, sonarr_id=2, title="Andor", followed=True)
        a1 = m.Season(number=1)
        a1.episodes += [
            m.Episode(sonarr_episode_id=10 + i, number=i, has_file=True) for i in (1, 2)
        ]
        andor.seasons.append(a1)
        idle = m.Series(instance=instance, sonarr_id=3, title="Idle", followed=True)
        server = m.MediaServer(kind="plex", name="Plex", url="http://p", token_enc="x")
        dennis = m.MediaUser(remote_id="1", name="Dennis", selected=True)
        anna = m.MediaUser(remote_id="2", name="Anna", selected=True)
        server.users = [dennis, anna]
        s.add_all([slime, andor, idle, server])
        s.flush()
        s.add_all(
            [
                m.WatchedEpisode(
                    user_id=dennis.id,
                    series_id=slime.id,
                    season_number=1,
                    episode_number=1,
                    watched_on=date(2026, 11, 1),
                ),
                m.WatchedEpisode(
                    user_id=dennis.id,
                    series_id=slime.id,
                    season_number=1,
                    episode_number=2,
                    watched_on=date(2026, 11, 8),
                ),
                m.WatchedEpisode(
                    user_id=anna.id,
                    series_id=slime.id,
                    season_number=1,
                    episode_number=1,
                    watched_on=date(2026, 11, 2),
                ),
                m.WatchedEpisode(
                    user_id=dennis.id,
                    series_id=andor.id,
                    season_number=1,
                    episode_number=1,
                    watched_on=date(2026, 10, 1),
                ),
                m.WatchedEpisode(
                    user_id=dennis.id,
                    series_id=andor.id,
                    season_number=1,
                    episode_number=2,
                    watched_on=date(2026, 10, 2),
                ),
            ]
        )
        s.commit()
    yield database
    database.dispose()


def by_title(s, title):
    return s.scalar(select(m.Series).where(m.Series.title == title))


def test_series_watch_per_user_and_episode(db):
    with db.session() as s:
        state = series_watch(s, by_title(s, "Slime"))
    assert state["enabled"] is True
    assert state["users"] == [
        {"name": "Dennis", "server": "Plex", "watched": 2, "last_watched": "2026-11-08"},
        {"name": "Anna", "server": "Plex", "watched": 1, "last_watched": "2026-11-02"},
    ]
    ids = {v["name"]: v["id"] for v in state["viewers"]}
    assert state["episodes"] == {"1x1": [ids["Dennis"], ids["Anna"]], "1x2": [ids["Dennis"]]}
    assert state["corrected"] == []
    assert state["unwatched_on_disk"] == 1  # E03 is on disk, nobody saw it; E04 has no file
    assert state["next_unwatched"] == {"season": 1, "episode": 3}


def test_caught_up_and_nobody_watching(db):
    with db.session() as s:
        andor = series_watch(s, by_title(s, "Andor"))
        idle = series_watch(s, by_title(s, "Idle"))
    assert (andor["unwatched_on_disk"], andor["next_unwatched"]) == (0, None)
    assert idle == {
        "enabled": True,
        "users": [],
        "episodes": {},
        "viewers": idle["viewers"],
        "corrected": [],
        "unwatched_on_disk": 0,
        "next_unwatched": None,
    }


@pytest.mark.parametrize(
    ("value", "titles"),
    [("started", ["Andor", "Slime"]), ("behind", ["Slime"]), ("caught_up", ["Andor"])],
)
def test_list_filters(db, value, titles):
    with db.session() as s:
        query = watch_filter(select(m.Series.title), value).order_by(m.Series.title)
        assert list(s.scalars(query)) == titles


def test_continue_watching_lists_started_series_with_unwatched_files(db):
    with db.session() as s:
        rows = continue_watching(s)
    assert rows == [
        {
            "series_id": rows[0]["series_id"],
            "title": "Slime",
            "poster_url": "p",
            "unwatched": 1,
            "next": {"season": 1, "episode": 3},
            "last_watched": "2026-11-08",
        }
    ]


def test_without_a_media_server_watch_state_is_off(db):
    with db.session() as s:
        s.query(m.MediaServer).delete()
        s.commit()
        assert series_watch(s, by_title(s, "Slime"))["enabled"] is False


def test_unwatched_counts_only_after_the_furthest_watched_episode(db):
    # Someone who watched E02 of a long-running show is not "300 behind" because of the
    # episodes before it; only what comes after the furthest watched episode counts.
    with db.session() as s:
        slime = by_title(s, "Slime")
        s.query(m.WatchedEpisode).filter_by(series_id=slime.id).delete()
        dennis = s.scalar(select(m.MediaUser).where(m.MediaUser.name == "Dennis"))
        s.add(
            m.WatchedEpisode(
                user_id=dennis.id, series_id=slime.id, season_number=1, episode_number=2
            )
        )
        s.commit()
        state = series_watch(s, slime)
        assert (state["unwatched_on_disk"], state["next_unwatched"]) == (
            1,
            {"season": 1, "episode": 3},
        )
        s.add(
            m.WatchedEpisode(
                user_id=dennis.id, series_id=slime.id, season_number=1, episode_number=3
            )
        )
        s.commit()
        state = series_watch(s, slime)
        assert (state["unwatched_on_disk"], state["next_unwatched"]) == (0, None)
        assert list(
            s.scalars(watch_filter(select(m.Series.title), "caught_up").order_by(m.Series.title))
        ) == ["Andor", "Slime"]


def test_caught_up_needs_a_followed_series_whose_episodes_are_known(db):
    # Finalarr keeps episode lists only for followed series; for the others "nothing
    # unwatched" would be a guess.
    with db.session() as s:
        by_title(s, "Andor").followed = False
        s.commit()
        caught_up = list(s.scalars(watch_filter(select(m.Series.title), "caught_up")))
        started = sorted(s.scalars(watch_filter(select(m.Series.title), "started")))
    assert caught_up == []
    assert started == ["Andor", "Slime"]
