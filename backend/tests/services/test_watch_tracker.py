from datetime import date

import pytest
from sqlalchemy import select

from finalarr.db import models as m
from finalarr.db.session import Database
from finalarr.services.watch_tracker import tracker_series, tracker_stats

TODAY = date(2026, 11, 25)  # a Wednesday; its week starts on Monday 2026-11-23


def _season(number, episodes, on_disk):
    season = m.Season(number=number)
    season.episodes += [
        m.Episode(sonarr_episode_id=number * 100 + i, number=i, has_file=i <= on_disk)
        for i in range(1, episodes + 1)
    ]
    return season


def _watch(s, user, series, episodes):
    s.add_all(
        m.WatchedEpisode(
            user_id=user.id,
            series_id=series.id,
            season_number=season,
            episode_number=episode,
            watched_on=day,
        )
        for season, episode, day in episodes
    )


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "f.db")
    database.migrate()
    with database.session() as s:
        instance = m.SonarrInstance(name="H", url="http://s", api_key_enc="x", webhook_token="t")
        # Slime: 4 episodes, 3 on disk; Dennis is at E02 (behind), Anna at E01.
        slime = m.Series(instance=instance, sonarr_id=1, title="Slime", followed=True, runtime=24)
        slime.seasons.append(_season(1, 4, 3))
        # Andor: ended, both episodes watched by Dennis (finished).
        andor = m.Series(
            instance=instance,
            sonarr_id=2,
            title="Andor",
            followed=True,
            runtime=45,
            status="ended",
        )
        andor.seasons.append(_season(1, 2, 2))
        # Bleach: continuing, Dennis watched E01 two months ago, E02 is on disk (abandoned).
        bleach = m.Series(instance=instance, sonarr_id=3, title="Bleach", followed=True, runtime=24)
        bleach.seasons.append(_season(1, 2, 2))
        # Dune: not followed, so its episodes are unknown.
        dune = m.Series(instance=instance, sonarr_id=4, title="Dune", runtime=60)
        server = m.MediaServer(kind="emby", name="Emby", url="http://e", token_enc="x")
        dennis = m.MediaUser(remote_id="1", name="Dennis", selected=True)
        anna = m.MediaUser(remote_id="2", name="Anna", selected=True)
        server.users = [dennis, anna]
        s.add_all([slime, andor, bleach, dune, server])
        s.flush()
        _watch(s, dennis, slime, [(1, 1, date(2026, 11, 2)), (1, 2, date(2026, 11, 24))])
        _watch(s, anna, slime, [(1, 1, date(2026, 11, 23))])
        _watch(s, dennis, andor, [(1, 1, None), (1, 2, date(2026, 11, 10))])
        _watch(s, dennis, bleach, [(1, 1, date(2026, 9, 20)), (0, 1, date(2026, 11, 24))])
        _watch(s, anna, dune, [(1, 1, date(2026, 11, 3))])
        s.commit()
    yield database
    database.dispose()


def user_id(s, name):
    return s.scalar(select(m.MediaUser.id).where(m.MediaUser.name == name))


def test_stats_for_everyone_count_each_episode_once(db):
    with db.session() as s:
        stats = tracker_stats(s, None, TODAY, weeks=4)
    # Slime E01 (twice), E02, Andor E01+E02, Bleach E01, Dune E01; the special never counts.
    assert stats["episodes"] == 6
    assert stats["minutes"] == 24 * 2 + 45 * 2 + 24 + 60
    assert stats["undated"] == 1
    assert stats["this_week"] == 2  # Slime E01 (Anna, Monday) and E02 (Dennis)
    assert stats["this_month"] == 4  # + Andor E02, Dune E01; Slime E01 counts once
    assert stats["weekly"] == [
        {"week": "2026-11-02", "episodes": 2},
        {"week": "2026-11-09", "episodes": 1},
        {"week": "2026-11-16", "episodes": 0},
        {"week": "2026-11-23", "episodes": 2},
    ]
    assert stats["series"] == {
        "started": 4,
        "behind": 2,
        "abandoned": 1,
        "caught_up": 0,
        "finished": 1,
        "unknown": 1,
    }


def test_stats_for_one_user(db):
    with db.session() as s:
        stats = tracker_stats(s, user_id(s, "Anna"), TODAY, weeks=2)
    assert (stats["episodes"], stats["this_week"], stats["minutes"]) == (2, 1, 84)
    assert stats["weekly"] == [
        {"week": "2026-11-16", "episodes": 0},
        {"week": "2026-11-23", "episodes": 1},
    ]
    assert stats["series"]["started"] == 2
    assert stats["series"]["behind"] == 1  # Slime: E02 and E03 on disk after her E01


def test_series_list_shows_what_is_missing(db):
    with db.session() as s:
        rows = tracker_series(s, None, TODAY)
    by_title = {row["title"]: row for row in rows}
    assert [row["title"] for row in rows] == ["Slime", "Andor", "Dune", "Bleach"]  # recent
    slime = by_title["Slime"]
    assert (slime["state"], slime["watched"], slime["unwatched"]) == ("behind", 2, 1)
    assert slime["next"] == {"season": 1, "episode": 3}
    assert slime["last_watched"] == "2026-11-24"
    assert by_title["Andor"]["state"] == "finished"
    assert by_title["Bleach"]["state"] == "abandoned"
    assert (by_title["Dune"]["state"], by_title["Dune"]["unwatched"]) == ("unknown", None)


@pytest.mark.parametrize(
    ("state", "sort", "titles"),
    [
        ("behind", "recent", ["Slime", "Bleach"]),  # abandoned is behind, too
        ("abandoned", "recent", ["Bleach"]),
        ("finished", "recent", ["Andor"]),
        ("all", "title", ["Andor", "Bleach", "Dune", "Slime"]),
        ("all", "open", ["Slime", "Bleach", "Andor", "Dune"]),
    ],
)
def test_series_list_filters_and_sorts(db, state, sort, titles):
    with db.session() as s:
        rows = tracker_series(s, None, TODAY, state=state, sort=sort)
    assert [row["title"] for row in rows] == titles


def test_a_caught_up_series_that_is_still_running(db):
    with db.session() as s:
        slime = s.scalar(select(m.Series).where(m.Series.title == "Slime"))
        _watch(s, s.get(m.MediaUser, user_id(s, "Dennis")), slime, [(1, 3, TODAY)])
        s.commit()
        rows = {r["title"]: r for r in tracker_series(s, None, TODAY)}
        stats = tracker_stats(s, None, TODAY)
    # E04 has no file yet: caught up, not finished.
    assert (rows["Slime"]["state"], rows["Slime"]["unwatched"]) == ("caught_up", 0)
    assert stats["series"]["caught_up"] == 1


def test_one_users_list_ignores_what_others_watched(db):
    with db.session() as s:
        rows = tracker_series(s, user_id(s, "Anna"), TODAY)
    slime = next(r for r in rows if r["title"] == "Slime")
    assert (slime["watched"], slime["unwatched"], slime["next"]) == (
        1,
        2,
        {"season": 1, "episode": 2},
    )


def test_unselected_users_do_not_count(db):
    with db.session() as s:
        s.get(m.MediaUser, user_id(s, "Anna")).selected = False
        s.commit()
        stats = tracker_stats(s, None, TODAY)
    assert stats["episodes"] == 5  # Slime E01+E02, Andor E01+E02, Bleach E01
