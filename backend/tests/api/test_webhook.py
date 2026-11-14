import base64

from sqlalchemy import select

from finalarr.db import models as m

DOWNLOAD = {"eventType": "Download", "series": {"id": 101, "title": "Slime"}}


def requests_in(app):
    with app.extensions["finalarr.db"].session() as s:
        return [(r.instance_id, r.sonarr_series_id) for r in s.scalars(select(m.ReconcileRequest))]


def test_download_queues_a_series_reconcile(client, app, instance):
    response = client.post(instance["webhook_path"], json=DOWNLOAD)
    assert response.status_code == 202
    assert requests_in(app) == [(instance["id"], 101)]


def test_repeated_triggers_coalesce(client, app, instance):
    for _ in range(3):
        client.post(instance["webhook_path"], json=DOWNLOAD)
    assert requests_in(app) == [(instance["id"], 101)]


def test_event_without_series_queues_a_full_reconcile(client, app, instance):
    assert client.post(instance["webhook_path"], json={"eventType": "Rename"}).status_code == 202
    assert requests_in(app) == [(instance["id"], 0)]


def test_test_event_is_acknowledged_without_work(client, app, instance):
    response = client.post(instance["webhook_path"], json={"eventType": "Test"})
    assert response.status_code == 200
    assert requests_in(app) == []


def test_the_scheduler_is_nudged(client, app, instance):
    nudged = []
    app.extensions["finalarr.nudge"] = lambda: nudged.append(True)
    client.post(instance["webhook_path"], json=DOWNLOAD)
    assert nudged == [True]


def test_unknown_token_is_404(client, instance):
    assert client.post("/webhook/sonarr/" + "0" * 64, json=DOWNLOAD).status_code == 404


def test_disabled_instance_is_404(client, api, instance):
    api.patch(f"/api/v1/instances/{instance['id']}", json={"enabled": False})
    assert client.post(instance["webhook_path"], json=DOWNLOAD).status_code == 404


def test_garbage_body_is_still_only_a_trigger(client, app, instance):
    response = client.post(instance["webhook_path"], data="not json", content_type="text/plain")
    assert response.status_code == 202
    assert requests_in(app) == [(instance["id"], 0)]


def test_series_id_must_be_a_positive_int(client, app, instance):
    client.post(
        instance["webhook_path"], json={"eventType": "Download", "series": {"id": "1; DROP"}}
    )
    assert requests_in(app) == [(instance["id"], 0)]


def test_oversized_body_is_rejected_before_parsing(client, instance):
    response = client.post(instance["webhook_path"], data="x" * (65 * 1024))
    assert response.status_code == 413


def test_basic_auth_is_enforced_when_configured(client, api, instance):
    api.patch(
        f"/api/v1/instances/{instance['id']}",
        json={"basic_user": "sonarr", "basic_password": "pw-123"},
    )
    assert client.post(instance["webhook_path"], json=DOWNLOAD).status_code == 401
    good = base64.b64encode(b"sonarr:pw-123").decode()
    bad = base64.b64encode(b"sonarr:nope").decode()
    path = instance["webhook_path"]
    assert (
        client.post(path, json=DOWNLOAD, headers={"Authorization": f"Basic {bad}"}).status_code
        == 401
    )
    assert (
        client.post(path, json=DOWNLOAD, headers={"Authorization": f"Basic {good}"}).status_code
        == 202
    )


def test_webhook_is_rate_limited_per_token(client, instance):
    codes = [client.post(instance["webhook_path"], json=DOWNLOAD).status_code for _ in range(61)]
    assert codes[:60] == [202] * 60
    assert codes[60] == 429


def test_ip_allowlist(settings, tmp_path):
    from finalarr.app import create_app

    from ..conftest import API_KEY

    app = create_app(
        settings=settings.model_copy(update={"webhook_allow": "192.168.1.10,10.0.0.0/8"}),
        static_dir=tmp_path,
    )
    client = app.test_client()
    created = client.post(
        "/api/v1/instances",
        json={"name": "C", "url": "http://s:1", "api_key": "k"},
        headers={"X-Api-Key": API_KEY},
    ).get_json()
    path = created["webhook_path"]
    denied = client.post(path, json=DOWNLOAD, environ_base={"REMOTE_ADDR": "192.168.1.50"})
    allowed = client.post(path, json=DOWNLOAD, environ_base={"REMOTE_ADDR": "10.1.2.3"})
    assert (denied.status_code, allowed.status_code) == (403, 202)


def test_malformed_basic_header_is_401(client, api, instance):
    api.patch(
        f"/api/v1/instances/{instance['id']}",
        json={"basic_user": "sonarr", "basic_password": "pw-123"},
    )
    response = client.post(
        instance["webhook_path"], json=DOWNLOAD, headers={"Authorization": "Basic !!!"}
    )
    assert response.status_code == 401


def test_unparseable_peer_is_denied_with_an_allowlist(app, client, instance):
    from finalarr.api.webhook import parse_allowlist

    app.extensions["finalarr.webhook_allow"] = parse_allowlist("10.0.0.0/8")
    response = client.post(
        instance["webhook_path"], json=DOWNLOAD, environ_base={"REMOTE_ADDR": "x"}
    )
    assert response.status_code == 403


def test_invalid_allowlist_refuses_to_start():
    import pytest

    from finalarr.config import ConfigError, load_settings

    with pytest.raises(ConfigError, match="WEBHOOK_ALLOW"):
        load_settings(
            {
                "FINALARR_API_KEY": "k" * 32,
                "FINALARR_SECRET_KEY": "x" * 43 + "=",
                "FINALARR_WEBHOOK_ALLOW": "not-an-ip",
            }
        )


def test_chunked_body_without_length_is_capped_too(client, app, instance):
    import io

    response = client.post(
        instance["webhook_path"],
        input_stream=io.BytesIO(b"x" * (200 * 1024)),
        headers={"Transfer-Encoding": "chunked", "Content-Type": "application/json"},
        environ_base={"wsgi.input_terminated": True},  # as gunicorn sets it for chunked
    )
    assert response.status_code == 413
    assert requests_in(app) == []


def test_any_accepted_call_records_when_sonarr_last_reached_finalarr(client, api, instance):
    assert api.get("/api/v1/instances").get_json()[0]["last_webhook_at"] is None
    client.post(instance["webhook_path"], json={"eventType": "Test"})
    assert api.get("/api/v1/instances").get_json()[0]["last_webhook_at"] is not None
