import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
import responses
from sqlalchemy import select

from finalarr.db import models as m
from finalarr.db.session import Database
from finalarr.services.news import NewsWatcher, normalize, title_matches
from finalarr.sources.feeds import FeedError, fetch_feed

NOW = datetime(2026, 11, 13, 12, tzinfo=UTC)
LIVECHART = (Path(__file__).parents[1] / "fixtures/feeds/livechart.xml").read_bytes()
URL = "https://www.livechart.me/feeds/headlines"


@responses.activate
def test_fetch_feed_parses_items():
    responses.get(URL, body=LIVECHART, content_type="application/rss+xml")
    items = fetch_feed(URL)
    assert len(items) == 4
    assert items[1].title.startswith('"Mushoku Tensei: Jobless Reincarnation" Season 3')
    assert items[1].link == "https://www.livechart.me/headlines/16573"
    assert items[1].published == datetime(2026, 11, 12, 9, tzinfo=UTC)


@responses.activate
def test_entity_attacks_are_rejected():
    bomb = (
        b'<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">'
        b'<!ENTITY lol2 "&lol;&lol;">]><rss><channel><item><title>&lol2;</title>'
        b"</item></channel></rss>"
    )
    responses.get(URL, body=bomb)
    with pytest.raises(FeedError):
        fetch_feed(URL)


@responses.activate
def test_http_errors_are_feed_errors():
    responses.get(URL, status=503)
    with pytest.raises(FeedError):
        fetch_feed(URL)


def test_normalize_and_match():
    assert (
        normalize("“Mushoku Tensei: Jobless Reincarnation” S3!")
        == "mushoku tensei jobless reincarnation s3"
    )
    headline = normalize('"Mushoku Tensei: Jobless Reincarnation" Season 3 Part 2 reveals premiere')
    assert title_matches(normalize("Mushoku Tensei: Jobless Reincarnation"), headline)
    assert title_matches(normalize("Mushoku Tensei"), headline)
    assert not title_matches(normalize("Mushoku Tensei III"), headline)
    assert not title_matches(normalize("Tensei"), headline)  # too short to be safe
    assert not title_matches(normalize("Bear"), normalize("The Bear Necessities of Life"))


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "f.db")
    database.migrate()
    with database.session() as s:
        instance = m.SonarrInstance(name="C", url="http://s:1", api_key_enc="x", webhook_token="t")
        s.add_all(
            [
                m.Series(
                    instance=instance,
                    sonarr_id=2,
                    title="Mushoku Tensei: Jobless Reincarnation",
                    followed=True,
                ),
                m.Series(
                    instance=instance, sonarr_id=3, title="SPY x FAMILY Code White", followed=True
                ),
                m.Series(
                    instance=instance,
                    sonarr_id=4,
                    title="Living It Up in Another World Until I Get Bored",
                    followed=False,
                ),
            ]
        )
        s.commit()
    yield database
    database.dispose()


def run(db, items, extra_titles=None):
    created = []
    NewsWatcher(
        db,
        [("livechart", lambda: items)],
        on_events=lambda s, e: created.extend(e),
        clock=lambda: NOW,
        extra_titles=extra_titles or (lambda s: {}),
    ).run()
    return created


@responses.activate
def test_recent_headlines_about_followed_series_become_hints(db):
    responses.get(URL, body=LIVECHART)
    items = fetch_feed(URL)
    created = run(db, items)
    assert len(created) == 1
    with db.session() as s:
        event = s.scalar(select(m.Event))
        payload = json.loads(event.payload_json)
    assert event.type == "news_mention"
    assert payload["link"] == "https://www.livechart.me/headlines/16573"
    assert payload["feed"] == "livechart"
    assert payload["title"] == "Mushoku Tensei: Jobless Reincarnation"
    assert run(db, items) == []


@responses.activate
def test_aliases_from_anilist_match_too_and_unsafe_links_are_dropped(db):
    responses.get(URL, body=LIVECHART)
    items = fetch_feed(URL)
    with db.session() as s:
        spy = s.scalar(select(m.Series).where(m.Series.sonarr_id == 3)).id
    created = run(db, items, extra_titles=lambda s: {spy: ["Spy x Family"]})
    titles = sorted(json.loads(e.payload_json)["title"] for e in created)
    assert titles == ["Mushoku Tensei: Jobless Reincarnation", "SPY x FAMILY Code White"]
    spy_event = next(e for e in created if "SPY" in e.payload_json)
    assert json.loads(spy_event.payload_json)["link"] is None


def test_failing_feed_is_skipped(db):
    def broken():
        raise FeedError("down")

    watcher = NewsWatcher(db, [("ann", broken)], clock=lambda: NOW)
    watcher.run()


def test_anilist_titles_come_from_the_cache(db):
    from finalarr.services.news import anilist_titles

    with db.session() as s:
        series = s.scalar(select(m.Series).where(m.Series.sonarr_id == 2))
        series.tvdb_id = 371310
        s.add(m.AnilistMapping(tvdb_id=371310, tvdb_season=1, anilist_id=108465, source="fribb"))
        s.add(
            m.AnilistCache(
                key="media:108465",
                body_json=json.dumps(
                    {
                        "id": 108465,
                        "title": {"romaji": "Mushoku Tensei", "english": None},
                        "synonyms": ["Jobless"],
                    }
                ),
                expires_at=NOW,
            )
        )
        s.commit()
        assert sorted(anilist_titles(s)[series.id]) == ["Jobless", "Mushoku Tensei"]


def test_news_can_be_switched_off(db):
    from finalarr.services.settings_store import save_settings

    with db.session() as s:
        save_settings(s, {"news_feeds": False})
        s.commit()
    calls = []
    NewsWatcher(db, [("x", lambda: calls.append(1) or [])], clock=lambda: NOW).run()
    assert calls == []


def test_merchandise_headlines_never_become_hints(db):
    from finalarr.sources.feeds import FeedItem

    items = [
        FeedItem(
            '"Mushoku Tensei: Jobless Reincarnation" Nendoroid figure opens for preorder',
            "https://x/1",
            NOW,
            None,
        ),
        FeedItem(
            '"Mushoku Tensei: Jobless Reincarnation" Season 3 Part 2 premieres January',
            "https://x/2",
            NOW,
            None,
        ),
    ]
    created = run(db, items)
    assert [json.loads(e.payload_json)["link"] for e in created] == ["https://x/2"]
