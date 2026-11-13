import json

import pytest
from sqlalchemy import select

from finalarr.db import models as m

from ..fakes import FakeSender

TOKEN = "123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"
TELEGRAM = {
    "name": "Telegram",
    "kind": "telegram",
    "fields": {"bot_token": TOKEN, "chat_id": "-100123"},
}


@pytest.fixture
def sender(app):
    fake = FakeSender()
    app.extensions["finalarr.delivery"].sender = fake
    return fake


@pytest.fixture
def channel(api, sender):
    response = api.post("/api/v1/channels", json=TELEGRAM)
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def test_create_never_returns_the_url(channel):
    assert channel["target"] == "tgram://***"
    assert TOKEN not in json.dumps(channel)
    assert (channel["language"], channel["event_filter"], channel["enabled"]) == ("de", [], True)


def test_url_is_encrypted_at_rest(app, channel):
    with app.extensions["finalarr.db"].session() as s:
        row = s.scalar(select(m.Channel))
    assert TOKEN not in row.apprise_url_enc


def test_invalid_preset_names_the_field(api, sender):
    response = api.post(
        "/api/v1/channels", json={**TELEGRAM, "fields": {"bot_token": "x", "chat_id": "1"}}
    )
    assert response.status_code == 400
    assert "fields.bot_token" in response.get_json()["error"]["fields"]


def test_list_patch_delete(api, channel):
    patched = api.patch(
        f"/api/v1/channels/{channel['id']}",
        json={
            "name": "Handy",
            "language": "en",
            "event_filter": ["season_complete"],
            "enabled": False,
        },
    ).get_json()
    assert (patched["name"], patched["language"], patched["event_filter"], patched["enabled"]) == (
        "Handy",
        "en",
        ["season_complete"],
        False,
    )
    assert [c["name"] for c in api.get("/api/v1/channels").get_json()] == ["Handy"]
    assert api.delete(f"/api/v1/channels/{channel['id']}").status_code == 204
    assert api.get("/api/v1/channels").get_json() == []


def test_patch_fields_rebuilds_the_url(api, app, channel):
    api.patch(
        f"/api/v1/channels/{channel['id']}",
        json={"kind": "telegram", "fields": {"bot_token": TOKEN, "chat_id": "42"}},
    )
    with app.extensions["finalarr.db"].session() as s:
        row = s.scalar(select(m.Channel))
    assert app.extensions["finalarr.secrets"].decrypt(row.apprise_url_enc).endswith("/42")


@pytest.mark.parametrize(
    "body",
    [{"language": "fr"}, {"event_filter": ["nope"]}, {"name": ""}, {"fields": {"chat_id": "1"}}],
)
def test_patch_validation(api, channel, body):
    assert api.patch(f"/api/v1/channels/{channel['id']}", json=body).status_code == 400


def test_test_message_saved_and_unsaved(api, channel, sender):
    assert api.post(f"/api/v1/channels/{channel['id']}/test").get_json() == {"ok": True}
    assert api.post("/api/v1/channels/test", json={**TELEGRAM, "language": "en"}).get_json() == {
        "ok": True
    }
    assert "Testnachricht" in sender.sent[0][1]
    assert "test message" in sender.sent[1][1]


def test_failed_test_is_a_friendly_502(api, channel, sender):
    sender.fail_with = "Unauthorized for tgram://***"
    response = api.post(f"/api/v1/channels/{channel['id']}/test")
    assert response.status_code == 502
    assert response.get_json()["error"] == {
        "code": "channel_failed",
        "message": "Unauthorized for tgram://***",
    }


def test_unknown_channel_404(api, sender):
    assert api.post("/api/v1/channels/9/test").status_code == 404
    assert api.patch("/api/v1/channels/9", json={}).status_code == 404


def test_resend_event(api, app, channel):
    with app.extensions["finalarr.db"].session() as s:
        event = m.Event(type="season_complete", fingerprint="x", payload_json="{}")
        s.add(event)
        s.commit()
        event_id = event.id
    body = api.post(f"/api/v1/events/{event_id}/resend", json={}).get_json()
    assert body == {"queued": 1}
    assert api.post("/api/v1/events/999/resend", json={}).status_code == 404


def test_new_events_get_deliveries_through_the_reconciler_hook(app, channel):
    hook = app.extensions["finalarr.reconciler"]._on_events
    with app.extensions["finalarr.db"].session() as s:
        event = m.Event(type="season_complete", fingerprint="y", payload_json="{}")
        s.add(event)
        s.flush()
        hook(s, [event])
        s.commit()
        assert len(s.scalars(select(m.Delivery)).all()) == 1


def test_unsaved_test_accepts_the_full_form_body(api, sender):
    body = {**TELEGRAM, "language": "de", "event_filter": ["season_complete"], "enabled": True}
    assert api.post("/api/v1/channels/test", json=body).status_code == 200


def test_api_literals_match_the_model_and_presets():
    from typing import get_args

    from finalarr.api.channels import EventName, Kind
    from finalarr.db.models import EVENT_TYPES
    from finalarr.notify.presets import KINDS

    assert set(get_args(Kind)) == set(KINDS)
    assert set(get_args(EventName)) == set(EVENT_TYPES)
