import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
import requests
import responses

from finalarr.sources.sonarr import (
    SonarrAuthError,
    SonarrClient,
    SonarrResponseError,
    SonarrUnreachable,
    validate_base_url,
)

FIXTURES = Path(__file__).parents[1] / "fixtures" / "sonarr"
BASE = "http://sonarr.local:8989"


def fixture(name):
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def client():
    return SonarrClient(BASE, "secret-key")


@responses.activate
def test_series_list_is_parsed_and_sends_the_key(client):
    responses.get(f"{BASE}/api/v3/series", json=fixture("series.json"))
    series = client.series_list()
    assert responses.calls[0].request.headers["X-Api-Key"] == "secret-key"
    slime = series[0]
    assert (slime.id, slime.tvdb_id, slime.series_type) == (101, 353712, "anime")
    assert slime.poster_url == "https://artworks.thetvdb.com/banners/p.jpg"
    assert [s.season_number for s in slime.seasons] == [0, 3]
    assert series[1].poster_url is None


@responses.activate
def test_episodes_are_parsed_with_optional_fields(client):
    responses.get(f"{BASE}/api/v3/episode", json=fixture("episodes_101.json"))
    episodes = client.episodes(101)
    assert responses.calls[0].request.url.endswith("/api/v3/episode?seriesId=101")
    first, second, finale, ova = episodes
    assert first.air_date_utc == datetime(2024, 4, 5, 15, tzinfo=UTC)
    assert first.absolute_episode_number == 49
    assert second.finale_type is None
    assert finale.finale_type == "season"
    assert ova.air_date_utc is None


@responses.activate
def test_system_status(client):
    responses.get(
        f"{BASE}/api/v3/system/status", json={"appName": "Sonarr", "version": "4.0.15.2941"}
    )
    assert client.system_status().version == "4.0.15.2941"


@responses.activate
@pytest.mark.parametrize("status", [401, 403])
def test_auth_errors(client, status):
    responses.get(f"{BASE}/api/v3/series", status=status)
    with pytest.raises(SonarrAuthError):
        client.series_list()


@responses.activate
def test_server_error_is_a_response_error(client):
    responses.get(f"{BASE}/api/v3/series", status=500, body="boom")
    with pytest.raises(SonarrResponseError, match="500"):
        client.series_list()


@responses.activate
def test_invalid_json_is_a_response_error(client):
    responses.get(f"{BASE}/api/v3/series", body="<html>")
    with pytest.raises(SonarrResponseError):
        client.series_list()


@responses.activate
def test_unexpected_shape_is_a_response_error(client):
    responses.get(f"{BASE}/api/v3/series", json=[{"id": "not-a-number"}])
    with pytest.raises(SonarrResponseError):
        client.series_list()


@responses.activate
def test_redirects_are_not_followed(client):
    responses.get(f"{BASE}/api/v3/series", status=302, headers={"Location": "http://evil/"})
    with pytest.raises(SonarrResponseError, match="redirect"):
        client.series_list()


@responses.activate
@pytest.mark.parametrize("error", [requests.ConnectionError("refused"), requests.Timeout("slow")])
def test_network_problems_are_unreachable(client, error):
    responses.get(f"{BASE}/api/v3/series", body=error)
    with pytest.raises(SonarrUnreachable):
        client.series_list()


def test_api_key_never_appears_in_errors(client):
    with responses.RequestsMock() as mock:
        mock.get(f"{BASE}/api/v3/series", status=500, body="secret-key leaked?")
        with pytest.raises(SonarrResponseError) as info:
            client.series_list()
    assert "secret-key" not in str(info.value)


@pytest.mark.parametrize(
    ("url", "normalised"),
    [
        ("http://sonarr:8989", "http://sonarr:8989"),
        ("https://tv.example.org/sonarr/", "https://tv.example.org/sonarr"),
    ],
)
def test_valid_base_urls(url, normalised):
    assert validate_base_url(url) == normalised


@pytest.mark.parametrize(
    "url", ["ftp://sonarr", "sonarr:8989", "http://", "http://user:pw@host", ""]
)
def test_invalid_base_urls(url):
    with pytest.raises(ValueError):
        validate_base_url(url)


def test_client_rejects_invalid_base_url():
    with pytest.raises(ValueError):
        SonarrClient("file:///etc/passwd", "k")


@responses.activate
def test_single_series(client):
    responses.get(f"{BASE}/api/v3/series/101", json=fixture("series.json")[0])
    assert client.series(101).title.startswith("That Time")
