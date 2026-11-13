import pytest

from finalarr.app import create_app


@pytest.fixture
def client(tmp_path, settings):
    (tmp_path / "index.html").write_text("<h1>Finalarr</h1>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    return create_app(settings=settings, static_dir=tmp_path).test_client()


def test_root_serves_index(client):
    assert b"Finalarr" in client.get("/").data


def test_client_side_route_falls_back_to_index(client):
    response = client.get("/series/42")
    assert response.status_code == 200
    assert b"Finalarr" in response.data


def test_existing_asset_is_served(client):
    assert client.get("/assets/app.js").data == b"console.log(1)"


def test_unknown_api_path_is_a_json_404_not_the_spa(client):
    from .conftest import API_KEY

    assert client.get("/api/v1/nope").status_code == 401
    response = client.get("/api/v1/nope", headers={"X-Api-Key": API_KEY})
    assert response.status_code == 404
    assert response.get_json() == {"error": {"code": "not_found", "message": "Not found"}}


def test_without_frontend_build_root_is_404(tmp_path, settings):
    client = create_app(settings=settings, static_dir=tmp_path / "missing").test_client()
    assert client.get("/").status_code == 404


def test_path_outside_static_dir_is_never_touched(client, tmp_path, monkeypatch):
    from pathlib import Path

    probed = []
    real_is_file = Path.is_file
    monkeypatch.setattr(Path, "is_file", lambda self: probed.append(self) or real_is_file(self))

    response = client.get("/..%2F..%2Fetc%2Fpasswd")

    assert response.status_code == 200
    assert b"Finalarr" in response.data
    assert all(p.resolve().is_relative_to(tmp_path) for p in probed)
