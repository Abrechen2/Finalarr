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
