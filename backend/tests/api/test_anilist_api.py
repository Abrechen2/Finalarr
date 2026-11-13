import pytest
from sqlalchemy import select

from finalarr.db import models as m
from finalarr.sources.anilist import AnilistRateLimited

from ..fakes import FakeAnilist


@pytest.fixture
def fake(app):
    fake = FakeAnilist()
    app.extensions["finalarr.anilist"]._client = fake
    return fake


@pytest.fixture
def season_id(app, instance):
    with app.extensions["finalarr.db"].session() as s:
        series = m.Series(
            instance_id=instance["id"],
            sonarr_id=2,
            tvdb_id=371310,
            title="Mushoku",
            series_type="anime",
            followed=True,
        )
        series.seasons.append(m.Season(number=2))
        s.add(series)
        s.commit()
        return series.seasons[0].id


def test_search_returns_candidates(api, fake):
    body = api.get("/api/v1/anilist/search?q=Mushoku").get_json()
    assert {c["id"] for c in body} >= {146065, 166873}
    first = body[0]
    assert set(first) == {"id", "title", "romaji", "format", "status", "episodes", "start_date"}


def test_search_needs_a_query(api, fake):
    assert api.get("/api/v1/anilist/search").status_code == 400


def test_search_when_anilist_is_limited(api, fake):
    fake.error = AnilistRateLimited(30)
    response = api.get("/api/v1/anilist/search?q=x")
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "anilist_unavailable"


def test_pin_stores_manual_mapping_and_enriches(api, app, fake, season_id):
    body = api.put(
        f"/api/v1/seasons/{season_id}/anilist", json={"anilist_ids": [146065, 166873]}
    ).get_json()
    assert body["anilist_count"] == 25
    assert [p["index"] for p in body["parts"]] == [1, 2]
    with app.extensions["finalarr.db"].session() as s:
        rows = s.scalars(select(m.AnilistMapping)).all()
        assert {(r.anilist_id, r.source) for r in rows} == {(146065, "manual"), (166873, "manual")}
        assert s.scalar(select(m.Series)).anilist_resolution == "manual"


def test_unpin_removes_manual_rows(api, app, fake, season_id):
    api.put(f"/api/v1/seasons/{season_id}/anilist", json={"anilist_ids": [146065]})
    api.put(f"/api/v1/seasons/{season_id}/anilist", json={"anilist_ids": []})
    with app.extensions["finalarr.db"].session() as s:
        assert s.scalars(select(m.AnilistMapping)).all() == []


def test_pin_saves_even_when_anilist_is_down(api, app, fake, season_id):
    fake.error = AnilistRateLimited(30)
    response = api.put(f"/api/v1/seasons/{season_id}/anilist", json={"anilist_ids": [146065]})
    assert response.status_code == 202
    with app.extensions["finalarr.db"].session() as s:
        assert s.scalar(select(m.AnilistMapping.anilist_id)) == 146065


def test_pin_validation(api, app, fake, season_id):
    assert (
        api.put(f"/api/v1/seasons/{season_id}/anilist", json={"anilist_ids": [0]}).status_code
        == 400
    )
    assert api.put("/api/v1/seasons/999/anilist", json={"anilist_ids": []}).status_code == 404


def test_pin_needs_a_tvdb_id(api, app, fake, season_id):
    with app.extensions["finalarr.db"].session() as s:
        s.scalar(select(m.Series)).tvdb_id = None
        s.commit()
    assert (
        api.put(f"/api/v1/seasons/{season_id}/anilist", json={"anilist_ids": [1]}).status_code
        == 409
    )


def test_detail_shows_the_mapping_per_season(api, app, fake, season_id):
    api.put(f"/api/v1/seasons/{season_id}/anilist", json={"anilist_ids": [146065, 166873]})
    with app.extensions["finalarr.db"].session() as s:
        series_id = s.scalar(select(m.Series.id))
    season = api.get(f"/api/v1/series/{series_id}").get_json()["seasons"][0]
    assert season["anilist_ids"] == [146065, 166873]
    assert season["anilist_pinned"] is True
    assert [(p["from"], p["to"]) for p in season["parts"]] == [(1, 13), (14, 25)]
