from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from finalarr.db import models as m
from finalarr.services.reconcile_queue import take_all


@pytest.fixture
def library(app, instance):
    """Three series; Slime has a season with episodes."""
    with app.extensions["finalarr.db"].session() as s:
        slime = m.Series(
            instance_id=instance["id"],
            sonarr_id=1,
            title="Slime",
            sort_title="slime",
            title_slug="slime",
            series_type="anime",
            year=2018,
            followed=True,
        )
        season = m.Season(number=3, state="airing", expected_count=4, expected_source="sonarr")
        slime.seasons.append(season)
        for n in range(1, 5):
            season.episodes.append(
                m.Episode(
                    sonarr_episode_id=100 + n,
                    number=n,
                    title=f"E{n}",
                    has_file=n <= 2,
                    air_date_utc=datetime(2026, 1, n * 7, tzinfo=UTC),
                    finale_type="season" if n == 4 else None,
                )
            )
        s.add_all(
            [
                slime,
                m.Series(
                    instance_id=instance["id"],
                    sonarr_id=2,
                    title="Andor",
                    sort_title="andor",
                    monitored=True,
                ),
                m.Series(
                    instance_id=instance["id"],
                    sonarr_id=3,
                    title="Zeta",
                    sort_title="zeta",
                    monitored=False,
                ),
            ]
        )
        s.commit()
        return {"slime": slime.id}


def titles(response):
    return [item["title"] for item in response.get_json()["items"]]


def test_list_sorted_with_season_summaries(api, library):
    body = api.get("/api/v1/series").get_json()
    assert [i["title"] for i in body["items"]] == ["Andor", "Slime", "Zeta"]
    slime = body["items"][1]
    assert slime["seasons"] == [
        {
            "id": slime["seasons"][0]["id"],
            "number": 3,
            "state": "airing",
            "expected": 4,
            "have": 2,
            "disputed": False,
        }
    ]
    assert body["next_cursor"] is None


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("followed=true", ["Slime"]),
        ("followed=false", ["Andor", "Zeta"]),
        ("q=sli", ["Slime"]),
        ("type=anime", ["Slime"]),
        ("type=standard", ["Andor", "Zeta"]),
    ],
)
def test_filters(api, library, query, expected):
    assert titles(api.get(f"/api/v1/series?{query}")) == expected


def test_cursor_pagination(api, library):
    first = api.get("/api/v1/series?limit=2").get_json()
    assert [i["title"] for i in first["items"]] == ["Andor", "Slime"]
    second = api.get(f"/api/v1/series?limit=2&cursor={first['next_cursor']}").get_json()
    assert [i["title"] for i in second["items"]] == ["Zeta"]
    assert second["next_cursor"] is None


def test_bad_query_values_are_400(api, library):
    assert api.get("/api/v1/series?limit=0").status_code == 400
    assert api.get("/api/v1/series?cursor=%%%").status_code == 400
    assert api.get("/api/v1/series?type=movie").status_code == 400


def test_detail_has_episodes_and_sonarr_link(api, library):
    body = api.get(f"/api/v1/series/{library['slime']}").get_json()
    assert body["sonarr_url"] == "http://sonarr:8989/series/slime"
    season = body["seasons"][0]
    assert [e["number"] for e in season["episodes"]] == [1, 2, 3, 4]
    assert season["episodes"][3]["finale_type"] == "season"
    assert season["episodes"][0]["air_date"].startswith("2026-01-07")


def test_detail_404(api):
    assert api.get("/api/v1/series/999").status_code == 404


def test_following_queues_a_reconcile_for_that_series(api, app, library, instance):
    with app.extensions["finalarr.db"].session() as s:
        andor = s.scalar(select(m.Series).where(m.Series.title == "Andor"))
    nudged = []
    app.extensions["finalarr.nudge"] = lambda: nudged.append(1)
    body = api.patch(f"/api/v1/series/{andor.id}", json={"followed": True}).get_json()
    assert body["followed"] is True
    with app.extensions["finalarr.db"].session() as s:
        assert take_all(s) == [(instance["id"], 2)]
    assert nudged == [1]


def test_rule_switches(api, library):
    body = api.patch(
        f"/api/v1/series/{library['slime']}",
        json={"include_specials": True, "respect_monitoring": False},
    ).get_json()
    assert (body["include_specials"], body["respect_monitoring"]) == (True, False)


def test_patch_rejects_unknown_fields(api, library):
    response = api.patch(f"/api/v1/series/{library['slime']}", json={"title": "x"})
    assert response.status_code == 400


def test_follow_all_monitored(api, app, library, instance):
    body = api.post("/api/v1/series/follow-monitored", json={}).get_json()
    assert body == {"followed": 1}
    assert titles(api.get("/api/v1/series?followed=true")) == ["Andor", "Slime"]
    with app.extensions["finalarr.db"].session() as s:
        assert take_all(s) == [(instance["id"], 0)]


def test_following_nudges_the_anilist_job(api, app, library):
    nudged = []
    app.extensions["finalarr.nudge_anilist"] = lambda: nudged.append(1)
    with app.extensions["finalarr.db"].session() as s:
        andor = s.scalar(select(m.Series).where(m.Series.title == "Andor"))
    api.patch(f"/api/v1/series/{andor.id}", json={"followed": True})
    api.post("/api/v1/series/follow-monitored", json={})
    assert nudged == [1, 1]


def test_tags_list_and_follow_by_tag(api, app, library):
    with app.extensions["finalarr.db"].session() as s:
        for row in s.scalars(select(m.Series)):
            row.tags_json = '["anime"]' if row.title in ("Zeta", "Slime") else '["kids"]'
        s.scalar(select(m.Series).where(m.Series.title == "Zeta")).monitored = True
        s.commit()
    assert api.get("/api/v1/series/tags").get_json() == ["anime", "kids"]
    assert api.post("/api/v1/series/follow-monitored", json={"tag": "anime"}).get_json() == {
        "followed": 1
    }
    assert titles(api.get("/api/v1/series?followed=true")) == ["Slime", "Zeta"]
    assert api.get("/api/v1/series").get_json()["items"][0]["tags"] == ["kids"]


def test_series_news_endpoint(api, app, library):
    from finalarr.sources.feeds import FeedItem

    seen = []

    def fake_fetch(url):
        seen.append(url)
        return [
            FeedItem(
                "Slime season 4 part 3 dated",
                "https://news.example/1",
                datetime.now(UTC),
                "Example",
            )
        ]

    app.extensions["finalarr.news_fetch"] = fake_fetch
    body = api.get(f"/api/v1/series/{library['slime']}/news?lang=en").get_json()
    assert body["web_enabled"] is True
    assert body["items"][0]["title"] == "Slime season 4 part 3 dated"
    assert "hl=en-US" in seen[0]
    api.patch("/api/v1/settings", json={"series_news_web": False})
    assert api.get(f"/api/v1/series/{library['slime']}/news").get_json() == {
        "items": [],
        "web_enabled": False,
        "web_error": False,
    }
    assert api.get("/api/v1/series/999/news").status_code == 404
    assert api.get(f"/api/v1/series/{library['slime']}/news?lang=xx").status_code == 400


def test_detail_carries_sonarr_details_and_delays(api, app, library):
    with app.extensions["finalarr.db"].session() as s:
        slime = s.get(m.Series, library["slime"])
        slime.overview, slime.network, slime.runtime = "Slime story", "Tokyo MX", 24
        slime.genres_json, slime.fanart_url = '["Anime"]', "https://img/fanart.jpg"
        slime.seasons[0].episodes[2].delayed_from = datetime(2026, 1, 14, tzinfo=UTC)
        s.commit()
    body = api.get(f"/api/v1/series/{library['slime']}").get_json()
    assert body["details"] == {
        "overview": "Slime story",
        "network": "Tokyo MX",
        "runtime": 24,
        "genres": ["Anime"],
        "fanart_url": "https://img/fanart.jpg",
    }
    assert body["waiting"]["key"]
    episodes = body["seasons"][0]["episodes"]
    assert episodes[2]["delayed_from"].startswith("2026-01-14")
    assert episodes[0]["delayed_from"] is None


def test_series_extras_endpoint(api, app, library):
    from finalarr.services.season_sources import JsonCache
    from finalarr.services.series_extras import ExtrasSources

    app.extensions["finalarr.extras"] = ExtrasSources(
        cache=JsonCache(app.extensions["finalarr.db"]), tvmaze=None
    )
    body = api.get(f"/api/v1/series/{library['slime']}/extras").get_json()
    assert set(body) >= {"next_episode", "trailer", "watch", "channel", "dub", "errors"}
    assert api.get("/api/v1/series/999/extras").status_code == 404


def follow_mode(app, title):
    with app.extensions["finalarr.db"].session() as s:
        row = s.scalar(select(m.Series).where(m.Series.title == title))
        return row.followed, row.follow_mode


def test_manual_follow_is_always_unfollow_is_never_and_auto_can_come_back(api, app, library):
    andor = api.get("/api/v1/series?q=Andor").get_json()["items"][0]
    assert andor["follow_mode"] == "auto"
    api.patch(f"/api/v1/series/{andor['id']}", json={"followed": True})
    assert follow_mode(app, "Andor") == (True, "always")
    api.patch(f"/api/v1/series/{andor['id']}", json={"followed": False})
    assert follow_mode(app, "Andor") == (False, "never")
    body = api.patch(f"/api/v1/series/{andor['id']}", json={"follow_mode": "auto"}).get_json()
    assert (body["followed"], body["follow_mode"]) == (False, "auto")
    assert api.patch(f"/api/v1/series/{andor['id']}", json={"follow_mode": "x"}).status_code == 400


def test_follow_all_respects_never_and_marks_always(api, app, library):
    with app.extensions["finalarr.db"].session() as s:
        s.scalar(select(m.Series).where(m.Series.title == "Andor")).follow_mode = "never"
        s.commit()
    assert api.post("/api/v1/series/follow-monitored", json={}).get_json() == {"followed": 0}
    assert follow_mode(app, "Andor") == (False, "never")


def _watch(app, title, episodes):
    with app.extensions["finalarr.db"].session() as s:
        series = s.scalar(select(m.Series).where(m.Series.title == title))
        server = m.MediaServer(kind="emby", name="Emby", url="http://e", token_enc="x")
        user = m.MediaUser(remote_id="u1", name="Dennis", selected=True)
        server.users = [user]
        s.add(server)
        s.flush()
        s.add_all(
            m.WatchedEpisode(
                user_id=user.id, series_id=series.id, season_number=1, episode_number=n
            )
            for n in episodes
        )
        s.commit()


def test_detail_and_list_carry_watched_state_and_filters(api, app, library):
    _watch(app, "Slime", [1, 2])
    detail = api.get(f"/api/v1/series/{library['slime']}").get_json()
    assert detail["watch"]["users"][0]["watched"] == 2
    viewer = detail["watch"]["viewers"][0]
    assert viewer["name"] == "Dennis"
    assert detail["watch"]["episodes"]["1x1"] == [viewer["id"]]
    listed = {i["title"]: i for i in api.get("/api/v1/series").get_json()["items"]}
    assert listed["Slime"]["watched"] == 2 and listed["Andor"]["watched"] == 0
    assert titles(api.get("/api/v1/series?watch=started")) == ["Slime"]
    assert titles(api.get("/api/v1/series?follow=auto")) == titles(api.get("/api/v1/series"))
    assert api.get("/api/v1/series?watch=nope").status_code == 400
    assert api.get("/api/v1/series?follow=nope").status_code == 400


def test_watched_corrections_endpoint(api, app, library):
    _watch(app, "Slime", [1])
    viewer = api.get(f"/api/v1/series/{library['slime']}").get_json()["watch"]["viewers"][0]
    url = f"/api/v1/series/{library['slime']}/watched"
    body = api.post(
        url, json={"user_id": viewer["id"], "episodes": [[1, 2], [1, 3]], "watched": True}
    )
    assert body.status_code == 200
    watch = body.get_json()
    assert sorted(watch["episodes"]) == ["1x1", "1x2", "1x3"]
    assert watch["corrected"] == ["1x2", "1x3"]
    undo = api.post(url, json={"user_id": viewer["id"], "episodes": [[1, 2]], "watched": None})
    assert undo.get_json()["corrected"] == ["1x3"]
    assert (
        api.post(url, json={"user_id": 999, "episodes": [[1, 1]], "watched": True}).status_code
        == 404
    )
    assert (
        api.post(url, json={"user_id": viewer["id"], "episodes": [], "watched": True}).status_code
        == 400
    )
    assert (
        api.post(
            "/api/v1/series/999/watched", json={"user_id": 1, "episodes": [[1, 1]], "watched": True}
        ).status_code
        == 404
    )
