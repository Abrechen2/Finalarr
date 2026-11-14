from datetime import date

import pytest
import requests
import responses

from finalarr.sources.tmdb import TMDB_URL, TmdbClient, TmdbError
from finalarr.sources.trakt import TRAKT_URL, TraktClient, TraktError


@responses.activate
def test_tmdb_find_and_seasons_with_v3_key():
    responses.get(f"{TMDB_URL}/find/371980", json={"tv_results": [{"id": 95396}]})
    responses.get(
        f"{TMDB_URL}/tv/95396",
        json={
            "seasons": [
                {"season_number": 0, "air_date": None, "episode_count": 1},
                {"season_number": 3, "air_date": "2027-03-05", "episode_count": 10},
                {"season_number": 4, "air_date": None, "episode_count": 0},
            ]
        },
    )
    client = TmdbClient("abc123")
    assert client.tv_id_for_tvdb(371980) == 95396
    assert "external_source=tvdb_id" in responses.calls[0].request.url
    assert "api_key=abc123" in responses.calls[0].request.url
    assert client.seasons(95396) == [(0, None, 1), (3, date(2027, 3, 5), 10), (4, None, None)]


@responses.activate
def test_tmdb_v4_token_goes_in_the_header():
    responses.get(f"{TMDB_URL}/find/1", json={"tv_results": []})
    assert TmdbClient("eyJhbGciOi.token").tv_id_for_tvdb(1) is None
    request = responses.calls[0].request
    assert request.headers["Authorization"] == "Bearer eyJhbGciOi.token"
    assert "api_key" not in request.url


@responses.activate
@pytest.mark.parametrize(
    "kwargs", [{"status": 401}, {"status": 500}, {"body": "x"}, {"body": requests.Timeout()}]
)
def test_tmdb_errors_never_leak_the_key(kwargs):
    responses.get(f"{TMDB_URL}/find/1", **kwargs)
    with pytest.raises(TmdbError) as info:
        TmdbClient("secret-key").tv_id_for_tvdb(1)
    assert "secret-key" not in str(info.value)


@responses.activate
def test_trakt_search_and_seasons():
    responses.get(
        f"{TRAKT_URL}/search/tvdb/371980",
        json=[{"type": "show", "show": {"ids": {"trakt": 154997}}}],
    )
    responses.get(
        f"{TRAKT_URL}/shows/154997/seasons",
        json=[
            {"number": 2, "episode_count": 10, "first_aired": "2025-01-17T02:00:00.000Z"},
            {"number": 3, "episode_count": 0, "first_aired": None},
        ],
    )
    client = TraktClient("client-id")
    assert client.show_id_for_tvdb(371980) == 154997
    assert responses.calls[0].request.headers["trakt-api-key"] == "client-id"
    assert responses.calls[0].request.headers["trakt-api-version"] == "2"
    assert client.seasons(154997) == [(2, date(2025, 1, 17), 10), (3, None, None)]
    assert "extended=full" in responses.calls[1].request.url


@responses.activate
def test_trakt_unknown_and_errors():
    responses.get(f"{TRAKT_URL}/search/tvdb/1", json=[])
    assert TraktClient("c").show_id_for_tvdb(1) is None
    responses.get(f"{TRAKT_URL}/shows/2/seasons", status=403)
    with pytest.raises(TraktError):
        TraktClient("c").seasons(2)


@responses.activate
def test_tmdb_extras_trailer_and_providers():
    responses.get(
        f"{TMDB_URL}/tv/95396",
        json={
            "videos": {
                "results": [
                    {"site": "YouTube", "type": "Teaser", "key": "tease"},
                    {"site": "Vimeo", "type": "Trailer", "key": "vim"},
                    {"site": "YouTube", "type": "Trailer", "key": "trail"},
                ]
            },
            "watch/providers": {
                "results": {
                    "DE": {
                        "link": "https://www.themoviedb.org/tv/95396/watch?locale=DE",
                        "flatrate": [{"provider_name": "Apple TV+"}],
                        "buy": [{"provider_name": "Amazon"}],
                    }
                }
            },
        },
    )
    extras = TmdbClient("k").extras(95396, "DE")
    assert "append_to_response=videos%2Cwatch%2Fproviders" in responses.calls[0].request.url
    assert extras.trailer == "trail"
    assert extras.providers == ("Apple TV+",)
    assert extras.link == "https://www.themoviedb.org/tv/95396/watch?locale=DE"
    assert TmdbClient("k").extras(95396, "US").providers == ()
