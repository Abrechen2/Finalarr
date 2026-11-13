import pytest

from ..conftest import API_KEY

AUTH = {"X-Api-Key": API_KEY}


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
def instance(api):
    response = api.post(
        "/api/v1/instances",
        json={"name": "Unraid", "url": "http://sonarr:8989", "api_key": "sonarr-secret-key"},
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()
