import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from finalarr.db import models as m
from finalarr.services.reconcile_queue import take_all


@pytest.fixture
def season(app, instance):
    with app.extensions["finalarr.db"].session() as s:
        series = m.Series(instance_id=instance["id"], sonarr_id=5, title="Slime", followed=True)
        season = m.Season(number=1)
        series.seasons.append(season)
        for n in (1, 2):
            season.episodes.append(
                m.Episode(
                    sonarr_episode_id=50 + n,
                    number=n,
                    has_file=n == 1,
                    air_date_utc=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=7 * n),
                )
            )
        s.add(series)
        s.commit()
        return {"season": season.id, "series": series.id}


@pytest.fixture
def events(app, season):
    with app.extensions["finalarr.db"].session() as s:
        rows = [
            m.Event(
                type=t,
                fingerprint=f"f{i}",
                series_id=season["series"],
                season_id=season["season"],
                payload_json=json.dumps({"title": title, "season": 1, "episodes": [i]}),
                created_at=datetime(2026, 2, 1, tzinfo=UTC) + timedelta(hours=i),
            )
            for i, (t, title) in enumerate(
                [
                    ("episodes_available", "Slime"),
                    ("season_complete", "Slime"),
                    ("episodes_available", "Andor"),
                ]
            )
        ]
        s.add_all(rows)
        s.commit()
        return [r.id for r in rows]


def test_events_newest_first_with_payload(api, events):
    body = api.get("/api/v1/events").get_json()
    assert [i["id"] for i in body["items"]] == list(reversed(events))
    first = body["items"][0]
    assert first["payload"]["title"] == "Andor"
    assert first["deliveries"] == []
    assert len(first["fingerprint"]) > 0


@pytest.mark.parametrize(
    ("query", "count"),
    [("type=season_complete", 1), ("q=slime", 2), ("since=2026-02-01T01:30:00Z", 1)],
)
def test_event_filters(api, events, season, query, count):
    assert len(api.get(f"/api/v1/events?{query}").get_json()["items"]) == count


def test_event_filter_by_series(api, events, season):
    assert len(api.get(f"/api/v1/events?series={season['series']}").get_json()["items"]) == 3


def test_event_pagination(api, events):
    first = api.get("/api/v1/events?limit=2").get_json()
    second = api.get(f"/api/v1/events?limit=2&cursor={first['next_cursor']}").get_json()
    assert [i["id"] for i in second["items"]] == [events[0]]
    assert second["next_cursor"] is None


def test_event_bad_filters(api):
    assert api.get("/api/v1/events?type=nope").status_code == 400
    assert api.get("/api/v1/events?since=yesterday").status_code == 400
    assert api.get("/api/v1/events?cursor=x").status_code == 400


def test_dry_run_returns_would_be_events_without_storing(api, app, season):
    url = f"/api/v1/seasons/{season['season']}/evaluate?dry_run=true"
    body = api.post(url).get_json()
    assert body["dry_run"] is True
    assert body["state"] == "aired"
    assert body["events"] == []  # first evaluation is the silent baseline
    with app.extensions["finalarr.db"].session() as s:
        stored = s.get(m.Season, season["season"])
        assert stored.memory_json is None
        assert s.scalar(select(m.Event)) is None


def test_dry_run_after_baseline_shows_the_pending_event(api, app, season):
    from finalarr.core.codec import dump_memory
    from finalarr.core.model import SeasonMemory

    with app.extensions["finalarr.db"].session() as s:
        stored = s.get(m.Season, season["season"])
        stored.memory_json = dump_memory(
            SeasonMemory("airing", True, frozenset(), frozenset(), None, 2, 3, False)
        )
        s.commit()
    body = api.post(f"/api/v1/seasons/{season['season']}/evaluate?dry_run=true").get_json()
    assert [e["type"] for e in body["events"]] == ["episodes_available"]
    assert body["events"][0]["payload"]["episodes"] == [1]


def test_real_evaluate_queues_a_fresh_reconcile(api, app, instance, season):
    assert api.post(f"/api/v1/seasons/{season['season']}/evaluate").status_code == 202
    with app.extensions["finalarr.db"].session() as s:
        assert take_all(s) == [(instance["id"], 5)]


def test_evaluate_unknown_season(api):
    assert api.post("/api/v1/seasons/999/evaluate?dry_run=true").status_code == 404
