import pytest
from cryptography.fernet import Fernet

from finalarr.app import create_app
from finalarr.config import Settings

API_KEY = "test-api-key-0123456789abcdef"
AUTH = {"X-Api-Key": API_KEY}


@pytest.fixture
def settings(tmp_path):
    return Settings(api_key=API_KEY, secret_key=Fernet.generate_key().decode(), data=tmp_path)


@pytest.fixture
def app(settings, tmp_path):
    return create_app(settings=settings, static_dir=tmp_path / "no-frontend")


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def api(client):
    """Test client that sends the API key on every call."""

    class Api:
        def __getattr__(self, method):
            def call(path, **kwargs):
                headers = {**AUTH, **kwargs.pop("headers", {})}
                return getattr(client, method)(path, headers=headers, **kwargs)

            return call

    return Api()


@pytest.fixture
def instance(api, app):
    response = api.post(
        "/api/v1/instances",
        json={"name": "Home", "url": "http://sonarr:8989", "api_key": "sonarr-secret-key"},
    )
    assert response.status_code == 201, response.get_json()
    from finalarr.services.reconcile_queue import take_all

    with app.extensions["finalarr.db"].session() as s:
        take_all(s)  # the first sync queued on creation; tests start from an empty queue
        s.commit()
    return response.get_json()
