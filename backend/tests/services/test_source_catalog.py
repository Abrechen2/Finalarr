import pytest

from finalarr.db.session import Database
from finalarr.services.settings_store import load_settings, save_settings
from finalarr.services.source_catalog import (
    CATALOG,
    disabled_sources,
    set_source,
    source_views,
)


@pytest.fixture
def session(tmp_path):
    db = Database(tmp_path / "f.db")
    db.migrate()
    with db.session() as s:
        yield s
    db.dispose()


class Keys:
    tmdb_api_key = "set"
    trakt_client_id = None
    animeschedule_token = None


def test_every_source_has_terms_and_https_links():
    assert len({s.id for s in CATALOG}) == len(CATALOG)
    assert all(s.url.startswith("https://") and s.terms_url.startswith("https://") for s in CATALOG)


def test_all_sources_on_by_default(session):
    views = source_views(session, Keys)
    assert all(v["enabled"] for v in views)
    by_id = {v["id"]: v for v in views}
    assert (by_id["tmdb"]["needs_key"], by_id["tmdb"]["configured"]) == (True, True)
    assert (by_id["trakt"]["needs_key"], by_id["trakt"]["configured"]) == (True, False)
    assert by_id["tvmaze"]["configured"] is True
    assert by_id["anilist"]["core"] is True


def test_switching_off_and_on(session):
    set_source(session, "tvmaze", False)
    set_source(session, "jikan", False)
    set_source(session, "jikan", True)
    assert disabled_sources(session) == {"tvmaze"}
    with pytest.raises(KeyError):
        set_source(session, "nope", False)


def test_google_news_follows_the_older_rules_switch(session):
    save_settings(session, {"series_news_web": False})
    assert "google_news" in disabled_sources(session)
    set_source(session, "google_news", True)
    assert load_settings(session)["series_news_web"] is True
    assert "google_news" not in disabled_sources(session)
    set_source(session, "google_news", False)
    assert load_settings(session)["series_news_web"] is False
