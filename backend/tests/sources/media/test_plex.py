from datetime import date

import pytest
import responses

from finalarr.sources.media import MediaError
from finalarr.sources.media.plex import PlexClient

URL = "http://plex:32400"


def item(key, season, n, viewed=1_794_000_000, show="100"):
    return {
        "type": "episode",
        "ratingKey": key,
        "grandparentRatingKey": show,
        "grandparentTitle": "Severance",
        "parentIndex": season,
        "index": n,
        "viewedAt": viewed,
        "accountID": 1,
    }


@responses.activate
def test_plex_identity_accounts_history_and_tvdb_guids():
    responses.get(
        f"{URL}/", json={"MediaContainer": {"friendlyName": "Home Plex", "version": "1.42.1"}}
    )
    responses.get(
        f"{URL}/accounts",
        json={
            "MediaContainer": {
                "Account": [
                    {"id": 0, "name": ""},
                    {"id": 1, "name": "dennis"},
                    {"id": 7, "name": "Kids"},
                ]
            }
        },
    )
    responses.get(
        f"{URL}/status/sessions/history/all",
        json={
            "MediaContainer": {
                "size": 2,
                "totalSize": 3,
                "Metadata": [item("1", 1, 1), item("2", 1, 2)],
            }
        },
    )
    responses.get(
        f"{URL}/status/sessions/history/all",
        json={
            "MediaContainer": {
                "size": 2,
                "totalSize": 3,
                "Metadata": [
                    item("1", 1, 1, viewed=1_700_000_000),
                    {"type": "movie", "ratingKey": "9"},
                ],
            }
        },
    )
    responses.get(
        f"{URL}/library/metadata/100",
        json={
            "MediaContainer": {
                "Metadata": [
                    {"ratingKey": "100", "Guid": [{"id": "imdb://tt1"}, {"id": "tvdb://371980"}]}
                ]
            }
        },
    )
    client = PlexClient(URL, "token", page_size=2)
    assert client.test() == "Home Plex 1.42.1"
    assert [(u.remote_id, u.name) for u in client.users()] == [("1", "dennis"), ("7", "Kids")]
    items = client.watched("1")
    # newest view per episode wins, movies are ignored
    assert [(i.series_tvdb, i.season, i.episode, i.watched_on) for i in items] == [
        (371980, 1, 1, date(2026, 11, 6)),
        (371980, 1, 2, date(2026, 11, 6)),
    ]
    first = responses.calls[2].request
    assert first.headers["X-Plex-Token"] == "token"
    assert first.headers["Accept"] == "application/json"
    assert "accountID=1" in first.url
    assert first.headers["X-Plex-Container-Start"] == "0"
    assert responses.calls[3].request.headers["X-Plex-Container-Start"] == "2"
    assert "includeGuids=1" in responses.calls[4].request.url


@responses.activate
def test_shows_without_tvdb_guid_stay_unmatched():
    responses.get(
        f"{URL}/status/sessions/history/all",
        json={
            "MediaContainer": {"size": 1, "totalSize": 1, "Metadata": [item("1", 1, 1, show="200")]}
        },
    )
    responses.get(
        f"{URL}/library/metadata/200",
        json={
            "MediaContainer": {
                "Metadata": [{"ratingKey": "200", "Guid": [{"id": "plex://show/abc"}]}]
            }
        },
    )
    [only] = PlexClient(URL, "t").watched("1")
    assert only.series_tvdb is None and only.series_title == "Severance"


@responses.activate
def test_plex_errors_never_leak_the_token():
    responses.get(f"{URL}/", status=401)
    with pytest.raises(MediaError) as info:
        PlexClient(URL, "secret-token").test()
    assert "secret-token" not in str(info.value)


@responses.activate
def test_legacy_tvdb_agent_guid_is_understood():
    responses.get(
        f"{URL}/status/sessions/history/all",
        json={
            "MediaContainer": {"size": 1, "totalSize": 1, "Metadata": [item("1", 2, 3, show="300")]}
        },
    )
    responses.get(
        f"{URL}/library/metadata/300",
        json={
            "MediaContainer": {
                "Metadata": [
                    {"ratingKey": "300", "guid": "com.plexapp.agents.thetvdb://81189?lang=en"}
                ]
            }
        },
    )
    [only] = PlexClient(URL, "t").watched("1")
    assert (only.series_tvdb, only.season, only.episode) == (81189, 2, 3)
