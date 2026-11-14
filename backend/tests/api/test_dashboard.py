import json
from datetime import UTC, datetime, timedelta

from finalarr.db import models as m

NOW = datetime.now(UTC)


def add_series(app, instance, title, state, offsets, files, followed=True, finale=None):
    with app.extensions["finalarr.db"].session() as s:
        series = m.Series(
            instance_id=instance["id"],
            sonarr_id=hash(title) % 10000,
            title=title,
            followed=followed,
        )
        season = m.Season(number=1, state=state, expected_count=len(offsets))
        series.seasons.append(season)
        for n, days in enumerate(offsets, start=1):
            season.episodes.append(
                m.Episode(
                    sonarr_episode_id=hash(title) % 1000 * 100 + n,
                    number=n,
                    has_file=n in files,
                    air_date_utc=NOW + timedelta(days=days),
                    finale_type="season" if n == finale else None,
                )
            )
        s.add(series)
        s.commit()
        return series.id


def test_onboarding_flags_on_an_empty_install(api):
    body = api.get("/api/v1/dashboard").get_json()
    assert body["onboarding"] == {"instance": False, "followed": False, "channel": False}
    assert body["airing"] == body["upcoming_finales"] == body["recent_events"] == []


def test_airing_seasons_and_upcoming_finales(api, app, instance):
    add_series(app, instance, "Slime", "airing", [-14, -7, 7, 14], {1, 2}, finale=4)
    add_series(app, instance, "Andor", "airing", [-3, 3, 30], {1})
    add_series(app, instance, "Done", "complete", [-30, -20], {1, 2})
    add_series(app, instance, "Old gaps", "aired", [-300, -293], {1})
    add_series(app, instance, "Ignored", "airing", [-1, 1], set(), followed=False)
    body = api.get("/api/v1/dashboard").get_json()
    airing = [(a["title"], a["have"], a["expected"]) for a in body["airing"]]
    assert airing == [("Andor", 1, 3), ("Slime", 2, 4)]  # sorted by next air date
    assert body["airing"][0]["next_air_date"][:10] == (NOW + timedelta(days=3)).date().isoformat()
    assert [a["next_episode"] for a in body["airing"]] == [2, 3]
    finales = [(f["title"], f["episode"]) for f in body["upcoming_finales"]]
    assert finales == [("Slime", 4), ("Andor", 3)]
    assert body["onboarding"] == {"instance": True, "followed": True, "channel": False}


def test_recent_events_are_the_latest_ten(api, app):
    with app.extensions["finalarr.db"].session() as s:
        for i in range(12):
            s.add(
                m.Event(
                    type="episodes_available",
                    fingerprint=str(i),
                    payload_json=json.dumps({"title": str(i)}),
                )
            )
        s.commit()
    events = api.get("/api/v1/dashboard").get_json()["recent_events"]
    assert len(events) == 10
    assert events[0]["payload"]["title"] == "11"
