import json
from datetime import date
from pathlib import Path

import pytest
import requests
import responses

from finalarr.sources.tvmaze import TVMAZE_URL, TvmazeClient, TvmazeError

SEASONS = json.loads(
    (Path(__file__).parents[1] / "fixtures/tvmaze/severance_seasons.json").read_text()
)


@pytest.fixture
def client():
    return TvmazeClient(sleep=lambda _s: None)


@responses.activate
def test_lookup_reads_the_show_id_from_the_redirect(client):
    responses.get(
        f"{TVMAZE_URL}/lookup/shows",
        status=301,
        headers={"Location": "https://api.tvmaze.com/shows/44933"},
    )
    assert client.show_id_for_tvdb(371980) == 44933
    assert "thetvdb=371980" in responses.calls[0].request.url


@responses.activate
def test_lookup_unknown_is_none(client):
    responses.get(f"{TVMAZE_URL}/lookup/shows", status=404)
    assert client.show_id_for_tvdb(1) is None


@responses.activate
def test_lookup_redirect_elsewhere_is_rejected(client):
    responses.get(
        f"{TVMAZE_URL}/lookup/shows",
        status=301,
        headers={"Location": "https://evil.example/shows/1"},
    )
    with pytest.raises(TvmazeError):
        client.show_id_for_tvdb(1)


@responses.activate
def test_seasons_are_parsed(client):
    responses.get(f"{TVMAZE_URL}/shows/44933/seasons", json=SEASONS)
    seasons = client.seasons(44933)
    assert [(s.number, s.premiere_date, s.episode_order) for s in seasons][:2] == [
        (1, date(2022, 2, 18), 9),
        (2, date(2025, 1, 17), 10),
    ]
    assert (seasons[2].number, seasons[2].premiere_date) == (3, None)


@responses.activate
def test_429_waits_and_retries_once(client):
    waits = []
    client = TvmazeClient(sleep=waits.append)
    responses.get(f"{TVMAZE_URL}/shows/1/seasons", status=429, headers={"Retry-After": "3"})
    responses.get(f"{TVMAZE_URL}/shows/1/seasons", json=[])
    assert client.seasons(1) == []
    assert waits == [3]


@responses.activate
@pytest.mark.parametrize(
    "kwargs",
    [{"status": 500}, {"body": "nope"}, {"body": requests.ConnectionError()}, {"status": 429}],
)
def test_errors(client, kwargs):
    responses.get(f"{TVMAZE_URL}/shows/1/seasons", **kwargs)
    with pytest.raises(TvmazeError):
        client.seasons(1)


def test_own_budget_waits_instead_of_failing():
    waits = []
    clock = {"t": 0.0}

    def sleep(seconds):
        waits.append(seconds)
        clock["t"] += seconds

    client = TvmazeClient(sleep=sleep, clock=lambda: clock["t"], budget=(2, 10))
    with responses.RequestsMock() as mock:
        mock.get(f"{TVMAZE_URL}/shows/1/seasons", json=[])
        for _ in range(3):
            client.seasons(1)
    assert waits and sum(waits) >= 10


@responses.activate
def test_show_info_with_next_episode(client):
    responses.get(
        f"{TVMAZE_URL}/shows/44933",
        json={
            "network": None,
            "webChannel": {"name": "Apple TV+"},
            "_embedded": {
                "nextepisode": {"season": 3, "number": 1, "airstamp": "2027-03-05T02:00:00+00:00"}
            },
        },
    )
    show = client.show(44933)
    assert "embed=nextepisode" in responses.calls[0].request.url
    assert show.channel == "Apple TV+"
    assert (show.next_season, show.next_number) == (3, 1)
    assert show.next_at.isoformat() == "2027-03-05T02:00:00+00:00"


@responses.activate
def test_show_info_network_without_next_episode(client):
    responses.get(f"{TVMAZE_URL}/shows/1", json={"network": {"name": "CBS"}, "webChannel": None})
    show = client.show(1)
    assert (show.channel, show.next_at) == ("CBS", None)
