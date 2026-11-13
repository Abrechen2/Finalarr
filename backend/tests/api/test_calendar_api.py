from datetime import UTC, datetime, timedelta

import pytest

from finalarr.db import models as m


@pytest.fixture
def show(app, instance):
    now = datetime.now(UTC)
    with app.extensions["finalarr.db"].session() as s:
        series = m.Series(instance_id=instance["id"], sonarr_id=1, title="Slime", followed=True)
        season = m.Season(number=3, expected_count=2)
        season.episodes += [
            m.Episode(sonarr_episode_id=1, number=1, air_date_utc=now + timedelta(days=2)),
            m.Episode(
                sonarr_episode_id=2,
                number=2,
                air_date_utc=now + timedelta(days=9),
                finale_type="season",
            ),
        ]
        series.seasons.append(season)
        s.add(series)
        s.commit()
        return series.id


def test_calendar_range(api, show):
    today = datetime.now(UTC).date()
    body = api.get(f"/api/v1/calendar?start={today}&end={today + timedelta(days=30)}").get_json()
    assert [(e["episode"], e["kind"]) for e in body["entries"]] == [(1, "premiere"), (2, "finale")]
    assert body["entries"][0]["series_id"] == show
    assert body["entries"][0]["all_day"] is False


@pytest.mark.parametrize(
    "query",
    [
        "",
        "start=2026-01-01",
        "start=x&end=y",
        "start=2026-01-01&end=2026-06-01",
        "start=2026-02-01&end=2026-01-01",
    ],
)
def test_calendar_range_validation(api, query):
    assert api.get(f"/api/v1/calendar?{query}").status_code == 400


def test_calendar_settings(api, show):
    api.patch("/api/v1/settings", json={"calendar_scope": "finales"})
    today = datetime.now(UTC).date()
    body = api.get(f"/api/v1/calendar?start={today}&end={today + timedelta(days=30)}").get_json()
    assert [e["kind"] for e in body["entries"]] == ["finale"]
    assert api.patch("/api/v1/settings", json={"calendar_scope": "everything"}).status_code == 400
    assert api.patch("/api/v1/settings", json={"calendar_days_ahead": 2000}).status_code == 400


def test_series_calendar_switch(api, show):
    assert (
        api.patch(f"/api/v1/series/{show}", json={"calendar": False}).get_json()["calendar"]
        is False
    )


def test_feed_is_off_until_enabled(api, client):
    assert api.get("/api/v1/calendar/feed").get_json() == {
        "enabled": False,
        "path": None,
        "url": None,
    }
    assert api.post("/api/v1/calendar/feed/rotate").status_code == 409


def test_feed_lifecycle(api, client, show):
    body = api.put("/api/v1/calendar/feed", json={"enabled": True}).get_json()
    assert body["enabled"] is True
    path = body["path"]
    assert path.startswith("/ical/") and path.endswith(".ics")
    response = client.get(path)
    assert response.status_code == 200
    assert response.mimetype == "text/calendar"
    assert response.headers["Cache-Control"] == "private, max-age=300"
    assert response.headers["X-Robots-Tag"].startswith("noindex")
    assert response.headers["Referrer-Policy"] == "no-referrer"
    text = response.get_data(as_text=True)
    assert "SUMMARY:Slime S03E02 – Finale" in text
    assert "Season premiere" in client.get(path + "?lang=en").get_data(as_text=True)
    assert api.put("/api/v1/calendar/feed", json={"enabled": True}).get_json()["path"] == path
    rotated = api.post("/api/v1/calendar/feed/rotate").get_json()["path"]
    assert rotated != path
    assert client.get(path).status_code == 404
    assert client.get(rotated).status_code == 200
    api.put("/api/v1/calendar/feed", json={"enabled": False})
    assert client.get(rotated).status_code == 404


@pytest.mark.parametrize(
    "path", ["/ical/nope.ics", "/ical/" + "a" * 64 + ".ics", "/ical/" + "a" * 64]
)
def test_unknown_feed_paths_are_404(client, path):
    assert client.get(path).status_code == 404


def test_feed_is_rate_limited(api, client):
    path = api.put("/api/v1/calendar/feed", json={"enabled": True}).get_json()["path"]
    codes = [client.get(path).status_code for _ in range(31)]
    assert codes[-1] == 429


def test_feed_url_uses_the_public_base_when_configured(settings, tmp_path):
    from finalarr.app import create_app

    from ..conftest import API_KEY

    app = create_app(
        settings=settings.model_copy(update={"feed_url": "https://finalarr.example.org"}),
        static_dir=tmp_path,
    )
    client = app.test_client()
    body = client.put(
        "/api/v1/calendar/feed",
        json={"enabled": True},
        headers={"X-Api-Key": API_KEY, "X-Requested-With": "finalarr"},
    ).get_json()
    assert body["url"] == f"https://finalarr.example.org{body['path']}"


def test_feed_url_is_null_without_a_public_base(api):
    assert api.put("/api/v1/calendar/feed", json={"enabled": True}).get_json()["url"] is None
