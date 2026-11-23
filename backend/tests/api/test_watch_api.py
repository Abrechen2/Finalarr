from datetime import UTC, datetime

from finalarr.db import models as m


def _seed(app, selected=True):
    with app.extensions["finalarr.db"].session() as s:
        instance = m.SonarrInstance(name="H", url="http://s", api_key_enc="x", webhook_token="t")
        series = m.Series(instance=instance, sonarr_id=1, title="Slime", followed=True)
        season = m.Season(number=1)
        season.episodes += [m.Episode(sonarr_episode_id=i, number=i, has_file=True) for i in (1, 2)]
        series.seasons.append(season)
        server = m.MediaServer(kind="emby", name="Emby", url="http://e", token_enc="x")
        user = m.MediaUser(remote_id="1", name="Dennis", selected=selected)
        server.users = [user]
        s.add_all([series, server])
        s.flush()
        s.add(
            m.WatchedEpisode(
                user_id=user.id,
                series_id=series.id,
                season_number=1,
                episode_number=1,
                watched_on=datetime.now(UTC).date(),
            )
        )
        s.commit()
        return user.id


def test_stats_and_series(api, app):
    uid = _seed(app)
    stats = api.get("/api/v1/watch/stats?weeks=4").get_json()
    assert (stats["episodes"], stats["this_week"], len(stats["weekly"])) == (1, 1, 4)
    assert stats["users"] == [{"id": uid, "name": "Dennis", "server": "Emby"}]
    assert api.get(f"/api/v1/watch/stats?user={uid}").get_json()["episodes"] == 1
    rows = api.get("/api/v1/watch/series?state=behind&sort=open").get_json()
    assert [(r["title"], r["unwatched"], r["next"]) for r in rows] == [
        ("Slime", 1, {"season": 1, "episode": 2})
    ]


def test_bad_arguments(api, app):
    uid = _seed(app, selected=False)
    assert api.get(f"/api/v1/watch/stats?user={uid}").status_code == 404
    assert api.get("/api/v1/watch/stats?user=x").status_code == 404
    assert api.get("/api/v1/watch/stats?weeks=0").status_code == 400
    assert api.get("/api/v1/watch/stats?weeks=53").status_code == 400
    assert api.get("/api/v1/watch/series?state=nope").status_code == 400
    assert api.get("/api/v1/watch/series?sort=nope").status_code == 400


def test_needs_the_api_key(client):
    assert client.get("/api/v1/watch/stats").status_code == 401
