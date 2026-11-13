import json
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from finalarr.crypto import SecretBox
from finalarr.db import models as m
from finalarr.db.session import Database
from finalarr.services.delivery import BACKOFF, MAX_ATTEMPTS, DeliveryWorker, create_deliveries

from ..fakes import FakeSender

NOW = datetime(2026, 4, 1, 12, tzinfo=UTC)


@pytest.fixture
def env(tmp_path):
    db = Database(tmp_path / "f.db")
    db.migrate()
    box = SecretBox(Fernet.generate_key().decode())
    sender = FakeSender()
    clock = {"now": NOW}
    worker = DeliveryWorker(
        db, box, sender, clock=lambda: clock["now"], public_url="https://finalarr.lan"
    )
    yield db, box, sender, worker, clock
    db.dispose()


def add_channel(db, box, name="TG", url="tgram://1/2", **extra):
    with db.session() as s:
        channel = m.Channel(name=name, kind="telegram", apprise_url_enc=box.encrypt(url), **extra)
        s.add(channel)
        s.commit()
        return channel.id


def add_event(db, kind="episodes_available", series_id=None, **payload):
    with db.session() as s:
        event = m.Event(
            type=kind,
            fingerprint=f"{kind}{len(payload)}{series_id}",
            series_id=series_id,
            payload_json=json.dumps(
                {
                    "title": "Slime",
                    "season": 3,
                    "episodes": [5],
                    "have": 5,
                    "expected": 12,
                    **payload,
                }
            ),
        )
        s.add(event)
        s.flush()
        create_deliveries(s, [event], NOW)
        s.commit()
        return event.id


def deliveries(db):
    with db.session() as s:
        return [
            (d.channel.name, d.status, d.attempts, d.last_error)
            for d in s.scalars(select(m.Delivery).order_by(m.Delivery.id))
        ]


def test_only_enabled_matching_channels_get_deliveries(env):
    db, box, *_ = env
    add_channel(db, box, "all")
    add_channel(db, box, "off", enabled=False)
    add_channel(db, box, "complete-only", event_filter_json='["season_complete"]')
    add_event(db)
    assert [name for name, *_ in deliveries(db)] == ["all"]


def test_worker_sends_in_the_channel_language_with_links(env):
    db, box, sender, worker, _ = env
    add_channel(db, box, "de", url="tgram://1/de")
    add_channel(db, box, "en", url="tgram://1/en", language="en")
    add_event(db, series_id=None, sonarr_url="http://sonarr:8989/series/slime")
    worker.run()
    bodies = dict(sender.sent)
    assert "S03 E05 verfügbar (5/12)" in bodies["tgram://1/de"]
    assert "S03 E05 available (5/12)" in bodies["tgram://1/en"]
    assert "http://sonarr:8989/series/slime" in bodies["tgram://1/de"]
    assert [status for _, status, *_ in deliveries(db)] == ["sent", "sent"]


def test_finalarr_link_needs_a_series(env):
    db, box, sender, worker, _ = env
    add_channel(db, box)
    with db.session() as s:
        instance = m.SonarrInstance(name="C", url="http://s:1", api_key_enc="x", webhook_token="t")
        series = m.Series(instance=instance, sonarr_id=1, title="Slime")
        s.add(series)
        s.commit()
        sid = series.id
    add_event(db, series_id=sid)
    worker.run()
    assert f"https://finalarr.lan/series/{sid}" in sender.sent[0][1]


def test_failures_retry_with_backoff_then_fail(env):
    db, box, sender, worker, clock = env
    add_channel(db, box)
    add_event(db)
    sender.fail_with = "HTTP 401 for tgram://***"
    worker.run()
    assert deliveries(db) == [("TG", "pending", 1, "HTTP 401 for tgram://***")]
    worker.run()  # not due yet
    assert deliveries(db)[0][2] == 1
    for step in range(1, MAX_ATTEMPTS):
        clock["now"] += BACKOFF[step - 1]
        worker.run()
    assert deliveries(db)[0][1:3] == ("failed", MAX_ATTEMPTS)
    clock["now"] += timedelta(days=1)
    worker.run()
    assert deliveries(db)[0][2] == MAX_ATTEMPTS


def test_retry_succeeds(env):
    db, box, sender, worker, clock = env
    add_channel(db, box)
    add_event(db)
    sender.fail_with = "timeout"
    worker.run()
    sender.fail_with = None
    clock["now"] += BACKOFF[0]
    worker.run()
    assert deliveries(db)[0][1] == "sent"


def test_undecryptable_channel_fails_without_crashing(env):
    db, _box, _sender, worker, _ = env
    other = SecretBox(Fernet.generate_key().decode())
    add_channel(db, other)
    add_event(db)
    worker.run()
    status, error = deliveries(db)[0][1], deliveries(db)[0][3]
    assert status == "failed"
    assert "FINALARR_SECRET_KEY" in error


def test_resend_resets_and_adds_missing_channels(env):
    from finalarr.services.delivery import resend

    db, box, sender, worker, _ = env
    add_channel(db, box, "a")
    event_id = add_event(db)
    worker.run()
    add_channel(db, box, "b")
    with db.session() as s:
        resend(s, event_id, now=NOW)
        s.commit()
    assert [(n, st) for n, st, *_ in deliveries(db)] == [("a", "pending"), ("b", "pending")]
    worker.run()
    assert len(sender.sent) == 3


def test_resend_to_one_channel(env):
    from finalarr.services.delivery import resend

    db, box, _sender, worker, _ = env
    a = add_channel(db, box, "a")
    add_channel(db, box, "b")
    event_id = add_event(db)
    worker.run()
    with db.session() as s:
        resend(s, event_id, channel_id=a, now=NOW)
        s.commit()
    assert [(n, st) for n, st, *_ in deliveries(db)] == [("a", "pending"), ("b", "sent")]


def test_quiet_hours_defer_without_using_an_attempt(env):
    from zoneinfo import ZoneInfo

    db, box, sender, worker, clock = env
    worker._zone = ZoneInfo("UTC")
    add_channel(db, box, quiet_hours_json='{"start": "11:00", "end": "13:00"}')
    add_event(db)
    worker.run()  # NOW is 12:00 UTC: inside the window
    assert sender.sent == []
    with db.session() as s:
        delivery = s.scalar(select(m.Delivery))
        assert (delivery.status, delivery.attempts) == ("pending", 0)
        assert delivery.next_attempt_at.replace(tzinfo=UTC) == NOW.replace(hour=13)
    clock["now"] = NOW.replace(hour=13)
    worker.run()
    assert len(sender.sent) == 1
