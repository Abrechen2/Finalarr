import pytest
from sqlalchemy import select

from finalarr.db import models as m
from finalarr.sources.media import MediaError, MediaUserInfo


class FakeClient:
    def __init__(self, url, token, fail=False):
        self.url, self.token, self.fail = url, token, fail

    def test(self):
        if self.fail or self.token == "bad":
            raise MediaError("Emby rejected the token")
        return "Home Emby 4.9"

    def users(self):
        return [MediaUserInfo("u1", "Dennis"), MediaUserInfo("u2", "Anna")]

    def watched(self, user_id):
        return []


@pytest.fixture
def fake(app):
    made = []

    def factory(kind, url, token):
        made.append((kind, url, token))
        return FakeClient(url, token)

    app.extensions["finalarr.media_client"] = factory
    return made


BODY = {"kind": "emby", "name": "Emby", "url": "http://emby:8096", "token": "emby-secret-token"}


def test_add_tests_the_connection_lists_users_and_masks_the_token(api, app, fake):
    response = api.post("/api/v1/media-servers", json=BODY)
    assert response.status_code == 201, response.get_json()
    server = response.get_json()
    assert server["token"].startswith("***") and "emby-secret-token" not in str(server)
    assert server["version"] == "Home Emby 4.9"
    assert [(u["name"], u["selected"]) for u in server["users"]] == [
        ("Dennis", False),
        ("Anna", False),
    ]
    with app.extensions["finalarr.db"].session() as s:
        assert "emby-secret-token" not in s.scalar(select(m.MediaServer)).token_enc
    assert api.get("/api/v1/media-servers").get_json()[0]["id"] == server["id"]


def test_rejected_token_and_bad_input(api, fake):
    bad = api.post("/api/v1/media-servers", json=BODY | {"token": "bad"})
    assert bad.status_code == 502
    assert bad.get_json()["error"]["code"] == "media_unreachable"
    assert api.post("/api/v1/media-servers", json=BODY | {"kind": "kodi"}).status_code == 400
    assert api.post("/api/v1/media-servers", json=BODY | {"url": "ftp://x"}).status_code == 400
    assert api.post("/api/v1/media-servers/test", json=BODY).get_json() == {
        "version": "Home Emby 4.9"
    }


def test_select_users_and_deselecting_deletes_their_watch_data(api, app, fake):
    server = api.post("/api/v1/media-servers", json=BODY).get_json()
    user = server["users"][0]
    body = api.patch(
        f"/api/v1/media-servers/{server['id']}/users/{user['id']}", json={"selected": True}
    ).get_json()
    assert body["selected"] is True
    with app.extensions["finalarr.db"].session() as s:
        instance = m.SonarrInstance(name="H", url="http://s", api_key_enc="x", webhook_token="t")
        series = m.Series(instance=instance, sonarr_id=1, title="Slime")
        s.add(series)
        s.flush()
        s.add(
            m.WatchedEpisode(
                user_id=user["id"], series_id=series.id, season_number=1, episode_number=1
            )
        )
        s.commit()
    api.patch(f"/api/v1/media-servers/{server['id']}/users/{user['id']}", json={"selected": False})
    with app.extensions["finalarr.db"].session() as s:
        assert s.query(m.WatchedEpisode).count() == 0
    assert (
        api.patch(
            f"/api/v1/media-servers/{server['id']}/users/999", json={"selected": True}
        ).status_code
        == 404
    )


def test_patch_delete_and_sync(api, app, fake):
    server = api.post("/api/v1/media-servers", json=BODY).get_json()
    body = api.patch(f"/api/v1/media-servers/{server['id']}", json={"enabled": False}).get_json()
    assert body["enabled"] is False
    nudged = []
    app.extensions["finalarr.nudge_media"] = lambda: nudged.append(1)
    assert api.post(f"/api/v1/media-servers/{server['id']}/sync").status_code == 202
    assert nudged == [1]
    assert api.delete(f"/api/v1/media-servers/{server['id']}").status_code == 204
    assert api.get("/api/v1/media-servers").get_json() == []
    assert api.delete("/api/v1/media-servers/999").status_code == 404


def test_a_new_url_needs_the_token_again(api, fake):
    server = api.post("/api/v1/media-servers", json=BODY).get_json()
    response = api.patch(f"/api/v1/media-servers/{server['id']}", json={"url": "http://evil:1"})
    assert response.status_code == 400
    assert response.get_json()["error"]["fields"] == {"token": "required when the URL changes"}
    assert fake[-1][1] == "http://emby:8096"  # the stored token was never sent elsewhere
    ok = api.patch(
        f"/api/v1/media-servers/{server['id']}", json={"url": "http://emby2:8096", "token": "new"}
    )
    assert ok.status_code == 200 and fake[-1] == ("emby", "http://emby2:8096", "new")
