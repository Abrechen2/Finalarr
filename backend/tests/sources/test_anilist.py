import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
import requests
import responses

from finalarr.sources.anilist import (
    ANILIST_URL,
    AnilistClient,
    AnilistError,
    AnilistRateLimited,
)

FIXTURES = Path(__file__).parents[1] / "fixtures" / "anilist"


def batch():
    return json.loads((FIXTURES / "media_batch.json").read_text())


@responses.activate
def test_media_batch_parses_real_response():
    responses.post(ANILIST_URL, json=batch())
    media = AnilistClient().media_batch([146065, 166873, 178789])
    request = json.loads(responses.calls[0].request.body)
    assert request["variables"] == {"ids": [146065, 166873, 178789]}
    part2 = media[166873]
    assert (part2.episodes, part2.status, part2.format) == (12, "FINISHED", "TV")
    assert part2.start_date == date(2024, 4, 8)
    assert part2.title == "Mushoku Tensei: Jobless Reincarnation Season 2 Part 2"
    assert (("PREQUEL", 146065) in part2.relation_ids) and (
        ("SEQUEL", 178789) in part2.relation_ids
    )


@responses.activate
def test_batches_are_split_at_fifty_ids():
    responses.post(ANILIST_URL, json={"data": {"Page": {"media": []}}})
    AnilistClient().media_batch(list(range(1, 121)))
    sizes = [len(json.loads(c.request.body)["variables"]["ids"]) for c in responses.calls]
    assert sizes == [50, 50, 20]


@responses.activate
def test_partial_dates_and_next_airing():
    responses.post(
        ANILIST_URL,
        json={
            "data": {
                "Page": {
                    "media": [
                        {
                            "id": 5,
                            "format": "TV",
                            "status": "RELEASING",
                            "episodes": None,
                            "title": {"romaji": "X", "english": None},
                            "synonyms": [],
                            "startDate": {"year": 2027, "month": None, "day": None},
                            "endDate": {"year": None, "month": None, "day": None},
                            "nextAiringEpisode": {"episode": 3, "airingAt": 1800000000},
                            "relations": {"edges": []},
                        }
                    ]
                }
            }
        },
    )
    media = AnilistClient().media_batch([5])[5]
    assert media.start_date == date(2027, 1, 1)
    assert media.end_date is None
    assert media.next_airing_at == datetime.fromtimestamp(1800000000, UTC)


@responses.activate
def test_search_returns_candidates():
    responses.post(
        ANILIST_URL, json={"data": {"Page": {"media": batch()["data"]["Page"]["media"][:2]}}}
    )
    results = AnilistClient().search("Mushoku")
    assert json.loads(responses.calls[0].request.body)["variables"]["search"] == "Mushoku"
    assert len(results) == 2


@responses.activate
def test_429_raises_rate_limited_with_retry_after():
    responses.post(ANILIST_URL, status=429, headers={"Retry-After": "42"})
    with pytest.raises(AnilistRateLimited) as info:
        AnilistClient().media_batch([1])
    assert info.value.retry_after == 42


@responses.activate
def test_own_budget_stops_before_anilist_does():
    responses.post(ANILIST_URL, json={"data": {"Page": {"media": []}}})
    client = AnilistClient(budget_per_minute=2)
    client.search("a")
    client.search("b")
    with pytest.raises(AnilistRateLimited):
        client.search("c")
    assert len(responses.calls) == 2


@responses.activate
@pytest.mark.parametrize(
    "kwargs",
    [
        {"status": 500, "body": "x"},
        {"json": {"errors": [{"message": "bad"}]}},
        {"body": "not json"},
        {"body": requests.ConnectionError()},
    ],
)
def test_errors(kwargs):
    responses.post(ANILIST_URL, **kwargs)
    with pytest.raises(AnilistError):
        AnilistClient().media_batch([1])


def test_empty_batch_makes_no_request():
    assert AnilistClient().media_batch([]) == {}


@responses.activate
def test_trailer_and_streaming_links():
    responses.post(
        ANILIST_URL,
        json={
            "data": {
                "Page": {
                    "media": [
                        {
                            "id": 7,
                            "title": {"romaji": "G"},
                            "trailer": {"id": "VpMwWDgZqtI", "site": "youtube"},
                            "externalLinks": [
                                {"site": "Twitter", "url": "https://x.com/g", "type": "SOCIAL"},
                                {
                                    "site": "Crunchyroll",
                                    "url": "https://www.crunchyroll.com/series/G",
                                    "type": "STREAMING",
                                },
                                {
                                    "site": "Crunchyroll",
                                    "url": "https://www.crunchyroll.com/de/series/G",
                                    "type": "STREAMING",
                                },
                                {"site": "Evil", "url": "javascript:x", "type": "STREAMING"},
                            ],
                        },
                        {
                            "id": 8,
                            "title": {"romaji": "H"},
                            "trailer": {"id": "x", "site": "dailymotion"},
                        },
                    ]
                }
            }
        },
    )
    media = AnilistClient().media_batch([7, 8])
    assert "trailer" in json.loads(responses.calls[0].request.body)["query"]
    assert media[7].youtube_trailer == "VpMwWDgZqtI"
    assert media[7].streaming_links == [("Crunchyroll", "https://www.crunchyroll.com/series/G")]
    assert media[8].youtube_trailer is None
    assert media[8].streaming_links == []
