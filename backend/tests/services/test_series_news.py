import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
import responses

from finalarr.db import models as m
from finalarr.db.session import Database
from finalarr.services.season_sources import JsonCache
from finalarr.services.series_news import news_query, series_news
from finalarr.sources.feeds import fetch_feed, google_news_url

NOW = datetime(2026, 11, 14, tzinfo=UTC)
GOOGLE = (Path(__file__).parents[1] / "fixtures/feeds/google_news.xml").read_bytes()


def test_google_news_url_and_source():
    url = google_news_url('"Mushoku Tensei"', "de")
    assert (
        url == "https://news.google.com/rss/search?q=%22Mushoku+Tensei%22&hl=de&gl=DE&ceid=DE%3Ade"
    )
    assert "hl=en-US" in google_news_url("x", "en")


@responses.activate
def test_feed_items_carry_their_source():
    responses.get("https://news.google.com/rss/search", body=GOOGLE)
    items = fetch_feed(google_news_url('"Mushoku Tensei"', "de"))
    assert items[0].source == "Anime2You"
    assert "Mushoku Tensei" in items[0].title


@pytest.mark.parametrize(
    ("title", "series_type", "lang", "query"),
    [
        (
            "Mushoku Tensei: Jobless Reincarnation",
            "anime",
            "de",
            '"Mushoku Tensei" (Staffel OR Folge)',
        ),
        ("Severance", "standard", "en", '"Severance" series (season OR episode)'),
        ("24", "standard", "de", '"24" Serie (Staffel OR Folge)'),
        ("DAN DA DAN", "anime", "en", '"DAN DA DAN" (season OR episode)'),
        ("Frieren", "anime", "de", '"Frieren" anime (Staffel OR Folge)'),
    ],
)
def test_news_query(title, series_type, lang, query):
    assert news_query(title, series_type, lang) == query


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "f.db")
    database.migrate()
    with database.session() as s:
        instance = m.SonarrInstance(name="C", url="http://s:1", api_key_enc="x", webhook_token="t")
        series = m.Series(
            instance=instance,
            sonarr_id=2,
            title="Mushoku Tensei: Jobless Reincarnation",
            series_type="anime",
            followed=True,
        )
        s.add(series)
        s.flush()
        s.add_all(
            [
                m.Event(
                    type="sequel_announced",
                    fingerprint="a",
                    series_id=series.id,
                    created_at=datetime(2026, 11, 13, tzinfo=UTC),
                    payload_json=json.dumps(
                        {
                            "title": series.title,
                            "sequel_title": "Mushoku III Part 2",
                            "first_air": "2027-01-01",
                        }
                    ),
                ),
                m.Event(
                    type="episodes_available",
                    fingerprint="b",
                    series_id=series.id,
                    payload_json="{}",
                ),
            ]
        )
        s.commit()
    yield database
    database.dispose()


def news(db, fetch, web=True):
    with db.session() as s:
        series = s.query(m.Series).one()
        return series_news(
            s, series, "de", JsonCache(db, clock=lambda: NOW), fetch=fetch, web=web, now=NOW
        )


def test_series_news_combines_finalarr_events_and_web_headlines(db):
    calls = []

    def fetch(url):
        calls.append(url)
        from finalarr.sources.feeds import parse_feed

        return parse_feed(GOOGLE)

    result = news(db, fetch)
    assert [i["kind"] for i in result["items"]][:1] == ["event"]
    assert result["items"][0]["event_type"] == "sequel_announced"
    web = [i for i in result["items"] if i["kind"] == "web"]
    # the fixture's merchandise headlines (figure, fashion line) are filtered out
    assert [w["source"] for w in web] == ["Hypebeast", "Crunchyroll"]
    assert web[0]["link"].startswith("https://news.google.com/")
    assert all(
        i["event_type"] != "episodes_available" for i in result["items"] if i["kind"] == "event"
    )
    news(db, fetch)
    assert len(calls) == 1  # cached
    assert result["web_error"] is False


def test_web_search_off_or_failing(db):
    from finalarr.sources.feeds import FeedError

    assert all(i["kind"] == "event" for i in news(db, lambda url: [], web=False)["items"])

    def broken(url):
        raise FeedError("down")

    result = news(db, broken)
    assert result["web_error"] is True
    assert [i["kind"] for i in result["items"]] == ["event"]


def test_merchandise_headlines_are_filtered_out(db):
    from finalarr.sources.feeds import FeedItem

    def fetch(url):
        return [
            FeedItem(
                "Neue Figur von Roxy aus »Mushoku Tensei« angekündigt",
                "https://n/1",
                NOW,
                "Anime2You",
            ),
            FeedItem(
                "„Mushoku Tensei“ Staffel 3 Teil 2 startet 2027", "https://n/2", NOW, "Hypebeast"
            ),
        ]

    titles = [i["title"] for i in news(db, fetch)["items"] if i["kind"] == "web"]
    assert titles == ["„Mushoku Tensei“ Staffel 3 Teil 2 startet 2027"]
