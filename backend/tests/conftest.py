import pytest
from cryptography.fernet import Fernet

from finalarr.app import create_app
from finalarr.config import Settings

API_KEY = "test-api-key-0123456789abcdef"


@pytest.fixture
def settings(tmp_path):
    return Settings(api_key=API_KEY, secret_key=Fernet.generate_key().decode(), data=tmp_path)


@pytest.fixture
def app(settings, tmp_path):
    return create_app(settings=settings, static_dir=tmp_path / "no-frontend")


@pytest.fixture
def client(app):
    return app.test_client()
