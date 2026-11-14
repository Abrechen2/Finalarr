import pytest

from finalarr.db import models as m
from finalarr.services.reconcile_queue import take_all


@pytest.fixture
def season_id(app, instance):
    with app.extensions["finalarr.db"].session() as s:
        series = m.Series(instance_id=instance["id"], sonarr_id=8, title="Slime", followed=True)
        season = m.Season(number=1, anilist_count=24)
        series.seasons.append(season)
        s.add(series)
        s.commit()
        return season.id


def test_override_is_stored_and_queues_a_reconcile(api, app, instance, season_id):
    body = api.patch(f"/api/v1/seasons/{season_id}", json={"expected_override": 12}).get_json()
    assert body["expected_override"] == 12
    with app.extensions["finalarr.db"].session() as s:
        assert take_all(s) == [(instance["id"], 8)]


def test_override_can_be_cleared(api, season_id):
    api.patch(f"/api/v1/seasons/{season_id}", json={"expected_override": 12})
    body = api.patch(f"/api/v1/seasons/{season_id}", json={"expected_override": None}).get_json()
    assert body["expected_override"] is None


def test_parts_mode(api, season_id):
    assert (
        api.patch(f"/api/v1/seasons/{season_id}", json={"parts_mode": "parts"}).get_json()[
            "parts_mode"
        ]
        == "parts"
    )


@pytest.mark.parametrize(
    "body",
    [
        {"expected_override": 0},
        {"expected_override": 5000},
        {"parts_mode": "x"},
        {"state": "complete"},
    ],
)
def test_season_patch_validation(api, season_id, body):
    assert api.patch(f"/api/v1/seasons/{season_id}", json=body).status_code == 400


def test_season_patch_404(api):
    assert api.patch("/api/v1/seasons/999", json={"parts_mode": "parts"}).status_code == 404


def test_settings_defaults_and_update(api):
    body = api.get("/api/v1/settings").get_json()
    assert body["reconcile_interval_minutes"] == 30
    assert body["renotify_on_growth"] is False
    updated = api.patch(
        "/api/v1/settings", json={"renotify_on_growth": True, "stable_runs": 3}
    ).get_json()
    assert (updated["renotify_on_growth"], updated["stable_runs"]) == (True, 3)
    assert api.get("/api/v1/settings").get_json()["stable_runs"] == 3


@pytest.mark.parametrize(
    "body",
    [
        {"stable_runs": 0},
        {"reconcile_interval_minutes": 2},
        {"reconcile_interval_minutes": 2000},
        {"nope": 1},
        {"renotify_on_growth": "yes"},
    ],
)
def test_settings_validation(api, body):
    assert api.patch("/api/v1/settings", json=body).status_code == 400


def test_count_sources_endpoint(api, app, season_id):
    class Anilist:
        def media(self, ids):
            return {}

    app.extensions["finalarr.anilist"] = Anilist()
    body = api.get(f"/api/v1/seasons/{season_id}/count-sources").get_json()
    assert body["sources"][0]["source"] == "sonarr"
    assert api.get("/api/v1/seasons/999/count-sources").status_code == 404
