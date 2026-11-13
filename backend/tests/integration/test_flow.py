"""Webhook → durable request → drain → reconcile → event, through the real app."""

import json

from sqlalchemy import select

from finalarr.db import models as m

from ..conftest import AUTH
from ..fakes import FakeSonarr, make_episodes, make_series


def test_webhook_to_event(app, client, instance):
    sonarr = FakeSonarr()
    sonarr.add(make_series(101, "Slime"), make_episodes(101, 3, 2, set()))
    app.extensions["finalarr.reconciler"]._client_factory = lambda _i: sonarr
    scheduler = app.extensions["finalarr.scheduler"]

    scheduler.queue_full_syncs()
    scheduler.drain()
    with app.extensions["finalarr.db"].session() as s:
        s.scalar(select(m.Series)).followed = True
        s.commit()
    client.post(instance["webhook_path"], json={"eventType": "Download", "series": {"id": 101}})
    scheduler.drain()  # baseline for the newly followed series

    sonarr.episodes_by_series[101] = make_episodes(101, 3, 2, {1})
    client.post(instance["webhook_path"], json={"eventType": "Download", "series": {"id": 101}})
    scheduler.drain()

    with app.extensions["finalarr.db"].session() as s:
        events = s.scalars(select(m.Event)).all()
    assert [(e.type, json.loads(e.payload_json)["episodes"]) for e in events] == [
        ("episodes_available", [1])
    ]
    assert client.get("/api/v1/instances", headers=AUTH).get_json()[0]["last_error"] is None
