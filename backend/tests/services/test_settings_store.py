import pytest

from finalarr.core.model import Policy
from finalarr.db.session import Database
from finalarr.services.settings_store import DEFAULTS, load_settings, policy_from, save_settings


@pytest.fixture
def session(tmp_path):
    db = Database(tmp_path / "f.db")
    db.migrate()
    with db.session() as s:
        yield s
    db.dispose()


def test_defaults_when_nothing_is_stored(session):
    assert load_settings(session) == DEFAULTS
    assert policy_from(load_settings(session)) == Policy()


def test_saved_values_override_defaults(session):
    save_settings(session, {"renotify_on_growth": True, "reconcile_interval_minutes": 15})
    stored = load_settings(session)
    assert stored["renotify_on_growth"] is True
    assert stored["reconcile_interval_minutes"] == 15
    assert policy_from(stored).renotify_on_growth is True


def test_unknown_keys_are_rejected(session):
    with pytest.raises(KeyError):
        save_settings(session, {"nope": 1})
