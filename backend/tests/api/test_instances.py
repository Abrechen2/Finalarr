import responses
from sqlalchemy import select

from finalarr.db import models as m


def test_create_masks_the_key_and_issues_a_webhook_token(instance):
    assert instance["name"] == "Home"
    assert instance["api_key"] == "***-key"
    assert "sonarr-secret-key" not in str(instance)
    assert len(instance["webhook_token"]) == 64
    assert instance["webhook_path"] == f"/webhook/sonarr/{instance['webhook_token']}"


def test_key_is_encrypted_at_rest(app, instance):
    with app.extensions["finalarr.db"].session() as s:
        row = s.scalar(select(m.SonarrInstance))
    assert "sonarr-secret-key" not in row.api_key_enc


def test_list_and_get(api, instance):
    assert [i["id"] for i in api.get("/api/v1/instances").get_json()] == [instance["id"]]
    assert api.get(f"/api/v1/instances/{instance['id']}").get_json()["url"] == "http://sonarr:8989"


def test_unknown_instance_is_404(api):
    response = api.get("/api/v1/instances/999")
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "not_found"


def test_invalid_body_is_400_with_fields(api):
    response = api.post("/api/v1/instances", json={"name": "", "url": "ftp://x"})
    assert response.status_code == 400
    error = response.get_json()["error"]
    assert error["code"] == "validation"
    assert {"name", "url", "api_key"} <= set(error["fields"])


def test_duplicate_name_is_409(api, instance):
    response = api.post(
        "/api/v1/instances", json={"name": "Home", "url": "http://x:1", "api_key": "k"}
    )
    assert response.status_code == 409


def test_patch_keeps_the_key_unless_given(api, app, instance):
    api.patch(f"/api/v1/instances/{instance['id']}", json={"name": "Main", "enabled": False})
    body = api.get(f"/api/v1/instances/{instance['id']}").get_json()
    assert (body["name"], body["enabled"]) == ("Main", False)
    box = app.extensions["finalarr.secrets"]
    with app.extensions["finalarr.db"].session() as s:
        assert box.decrypt(s.scalar(select(m.SonarrInstance)).api_key_enc) == "sonarr-secret-key"


def test_patch_validates(api, instance):
    response = api.patch(f"/api/v1/instances/{instance['id']}", json={"url": "nope"})
    assert response.status_code == 400


def test_delete(api, instance):
    assert api.delete(f"/api/v1/instances/{instance['id']}").status_code == 204
    assert api.get("/api/v1/instances").get_json() == []


def test_rotate_token(api, instance):
    rotated = api.post(f"/api/v1/instances/{instance['id']}/rotate-token").get_json()
    assert rotated["webhook_token"] != instance["webhook_token"]


@responses.activate
def test_connection_test_reports_the_version(api, instance):
    responses.get("http://sonarr:8989/api/v3/system/status", json={"version": "4.0.15"})
    body = api.post(f"/api/v1/instances/{instance['id']}/test").get_json()
    assert body == {"ok": True, "version": "4.0.15"}
    assert responses.calls[0].request.headers["X-Api-Key"] == "sonarr-secret-key"


@responses.activate
def test_unsaved_connection_test_for_onboarding(api):
    responses.get("http://new:8989/api/v3/system/status", status=401)
    response = api.post("/api/v1/instances/test", json={"url": "http://new:8989", "api_key": "k"})
    assert response.status_code == 502
    assert response.get_json()["error"]["code"] == "sonarr_auth"


@responses.activate
def test_unreachable_sonarr_is_a_friendly_502(api, instance):
    import requests

    responses.get("http://sonarr:8989/api/v3/system/status", body=requests.ConnectionError())
    response = api.post(f"/api/v1/instances/{instance['id']}/test")
    assert response.status_code == 502
    assert response.get_json()["error"]["code"] == "sonarr_unreachable"


def test_sync_queues_a_full_reconcile(api, app, instance):
    assert api.post(f"/api/v1/instances/{instance['id']}/sync").status_code == 202
    with app.extensions["finalarr.db"].session() as s:
        request = s.scalar(select(m.ReconcileRequest))
    assert (request.instance_id, request.sonarr_series_id) == (instance["id"], 0)


def test_basic_auth_password_is_write_only(api, instance):
    api.patch(
        f"/api/v1/instances/{instance['id']}",
        json={"basic_user": "sonarr", "basic_password": "pw-123"},
    )
    body = api.get(f"/api/v1/instances/{instance['id']}").get_json()
    assert body["basic_user"] == "sonarr"
    assert body["basic_password_set"] is True
    assert "pw-123" not in str(body)


def test_non_object_body_is_400(api):
    response = api.post("/api/v1/instances", json=["x"])
    assert response.get_json()["error"]["code"] == "bad_request"


def test_patch_url_and_key(api, app, instance):
    api.patch(
        f"/api/v1/instances/{instance['id']}", json={"url": "http://other:1/", "api_key": "new-key"}
    )
    assert api.get(f"/api/v1/instances/{instance['id']}").get_json()["url"] == "http://other:1"
    with app.extensions["finalarr.db"].session() as s:
        row = s.scalar(select(m.SonarrInstance))
    assert app.extensions["finalarr.secrets"].decrypt(row.api_key_enc) == "new-key"


def test_sync_nudges_the_scheduler(api, app, instance):
    nudged = []
    app.extensions["finalarr.nudge"] = lambda: nudged.append(True)
    api.post(f"/api/v1/instances/{instance['id']}/sync")
    assert nudged == [True]


def test_queue_take_all_drains_in_order(app, instance):
    from finalarr.services.reconcile_queue import enqueue, take_all

    with app.extensions["finalarr.db"].session() as s:
        enqueue(s, instance["id"], 5)
        enqueue(s, instance["id"])
        assert take_all(s) == [(instance["id"], 5), (instance["id"], 0)]
        assert take_all(s) == []


def test_creating_an_instance_queues_a_first_sync(api, app):
    from finalarr.services.reconcile_queue import take_all

    nudged = []
    app.extensions["finalarr.nudge"] = lambda: nudged.append(1)
    created = api.post(
        "/api/v1/instances", json={"name": "B", "url": "http://b:1", "api_key": "k"}
    ).get_json()
    with app.extensions["finalarr.db"].session() as s:
        assert take_all(s) == [(created["id"], 0)]
    assert nudged == [1]


def test_a_new_url_needs_the_key_again(api, instance):
    # Otherwise a changed address would receive the stored Sonarr key on the next sync.
    response = api.patch(f"/api/v1/instances/{instance['id']}", json={"url": "http://evil:1"})
    assert response.status_code == 400
    assert response.get_json()["error"]["fields"] == {"api_key": "required when the URL changes"}
    ok = api.patch(
        f"/api/v1/instances/{instance['id']}", json={"url": "http://sonarr2:8989", "api_key": "k2"}
    )
    assert ok.status_code == 200
