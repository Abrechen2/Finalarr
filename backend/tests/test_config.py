import pytest
from cryptography.fernet import Fernet

from finalarr.config import ConfigError, load_settings

GOOD_KEY = "k" * 32


def env(**overrides):
    base = {"FINALARR_API_KEY": GOOD_KEY, "FINALARR_SECRET_KEY": Fernet.generate_key().decode()}
    return {**base, **overrides}


def test_loads_defaults():
    settings = load_settings(env())
    assert settings.port == 5790
    assert settings.language == "de"
    assert settings.api_key.get_secret_value() == GOOD_KEY


@pytest.mark.parametrize("missing", ["FINALARR_API_KEY", "FINALARR_SECRET_KEY"])
def test_missing_secret_refuses_to_start(missing):
    values = env()
    del values[missing]
    with pytest.raises(ConfigError, match=missing):
        load_settings(values)


def test_empty_api_key_refuses_to_start():
    with pytest.raises(ConfigError, match="FINALARR_API_KEY"):
        load_settings(env(FINALARR_API_KEY="   "))


def test_short_api_key_refuses_to_start():
    with pytest.raises(ConfigError, match="at least 20"):
        load_settings(env(FINALARR_API_KEY="short"))


def test_invalid_fernet_key_refuses_to_start():
    with pytest.raises(ConfigError, match="FINALARR_SECRET_KEY"):
        load_settings(env(FINALARR_SECRET_KEY="not-a-fernet-key"))


def test_error_message_never_contains_secret_values():
    secret = "super-secret-but-short"
    with pytest.raises(ConfigError) as info:
        load_settings(env(FINALARR_SECRET_KEY=secret))
    assert secret not in str(info.value)


def test_invalid_language_refuses_to_start():
    with pytest.raises(ConfigError, match="FINALARR_LANGUAGE"):
        load_settings(env(FINALARR_LANGUAGE="fr"))


def test_reads_process_environment(monkeypatch):
    for key, value in env(FINALARR_PORT="6000").items():
        monkeypatch.setenv(key, value)
    assert load_settings().port == 6000
