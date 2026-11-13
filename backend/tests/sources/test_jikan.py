from datetime import date

import pytest
import requests
import responses

from finalarr.sources.jikan import JIKAN_URL, JikanClient, JikanError


@pytest.fixture
def client():
    return JikanClient(sleep=lambda _s: None)


@responses.activate
def test_sequels_from_relations(client):
    responses.get(
        f"{JIKAN_URL}/anime/58789/relations",
        json={
            "data": [
                {
                    "relation": "Prequel",
                    "entry": [{"mal_id": 55888, "type": "anime", "name": "S2"}],
                },
                {
                    "relation": "Sequel",
                    "entry": [
                        {"mal_id": 61234, "type": "anime", "name": "S3 Part 2"},
                        {"mal_id": 1, "type": "manga", "name": "x"},
                    ],
                },
            ]
        },
    )
    assert client.sequel_ids(58789) == [61234]


@responses.activate
def test_anime_details(client):
    responses.get(
        f"{JIKAN_URL}/anime/61234",
        json={
            "data": {
                "mal_id": 61234,
                "title": "Mushoku Tensei III Part 2",
                "type": "TV",
                "status": "Not yet aired",
                "episodes": None,
                "aired": {"from": "2027-01-01T00:00:00+00:00"},
            }
        },
    )
    anime = client.anime(61234)
    assert (anime.title, anime.type, anime.upcoming, anime.start_date, anime.episodes) == (
        "Mushoku Tensei III Part 2",
        "TV",
        True,
        date(2027, 1, 1),
        None,
    )


@responses.activate
def test_finished_is_not_upcoming(client):
    responses.get(
        f"{JIKAN_URL}/anime/1",
        json={
            "data": {
                "mal_id": 1,
                "title": "x",
                "type": "TV",
                "status": "Finished Airing",
                "aired": {"from": None},
            }
        },
    )
    assert client.anime(1).upcoming is False
    assert client.anime(1).start_date is None


@responses.activate
def test_429_waits_and_retries(client):
    waits = []
    client = JikanClient(sleep=waits.append)
    responses.get(f"{JIKAN_URL}/anime/1/relations", status=429)
    responses.get(f"{JIKAN_URL}/anime/1/relations", json={"data": []})
    assert client.sequel_ids(1) == []
    assert waits


@responses.activate
@pytest.mark.parametrize("kwargs", [{"status": 500}, {"body": "x"}, {"body": requests.Timeout()}])
def test_errors(client, kwargs):
    responses.get(f"{JIKAN_URL}/anime/1/relations", **kwargs)
    with pytest.raises(JikanError):
        client.sequel_ids(1)
