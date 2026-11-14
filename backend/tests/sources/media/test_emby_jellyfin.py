from datetime import date

import pytest
import requests
import responses

from finalarr.sources.media import MediaError, client_for
from finalarr.sources.media.emby import EmbyClient, JellyfinClient

URL = "http://emby:8096"


def episode(n, season=1, series="s1", played="2026-11-10T20:15:00.0000000Z"):
    return {
        "Id": f"e{season}{n}",
        "Type": "Episode",
        "SeriesId": series,
        "SeriesName": "Slime",
        "ParentIndexNumber": season,
        "IndexNumber": n,
        "UserData": {"Played": True, "LastPlayedDate": played},
    }


@responses.activate
def test_emby_test_users_and_watched_episodes_with_paging_and_tvdb_ids():
    responses.get(f"{URL}/System/Info", json={"ServerName": "Home Emby", "Version": "4.9.1"})
    responses.get(
        f"{URL}/Users", json=[{"Id": "u1", "Name": "Dennis"}, {"Id": "u2", "Name": "Anna"}]
    )
    page1 = {"Items": [episode(1), episode(2)], "TotalRecordCount": 3}
    page2 = {"Items": [episode(3, played=None)], "TotalRecordCount": 3}
    responses.get(f"{URL}/Users/u1/Items", json=page1)
    responses.get(f"{URL}/Users/u1/Items", json=page2)
    responses.get(
        f"{URL}/Users/u1/Items",
        json={"Items": [{"Id": "s1", "Name": "Slime", "ProviderIds": {"Tvdb": "1007"}}]},
    )
    client = EmbyClient(URL, "key", page_size=2)
    assert client.test() == "Home Emby 4.9.1"
    assert [(u.remote_id, u.name) for u in client.users()] == [("u1", "Dennis"), ("u2", "Anna")]
    items = client.watched("u1")
    assert [(i.series_tvdb, i.season, i.episode, i.watched_on) for i in items] == [
        (1007, 1, 1, date(2026, 11, 10)),
        (1007, 1, 2, date(2026, 11, 10)),
        (1007, 1, 3, None),
    ]
    assert items[0].series_title == "Slime"
    first = responses.calls[2].request
    assert first.headers["X-Emby-Token"] == "key"
    assert "IsPlayed=true" in first.url and "IncludeItemTypes=Episode" in first.url
    assert "StartIndex=0" in first.url and "StartIndex=2" in responses.calls[3].request.url
    assert "Ids=s1" in responses.calls[4].request.url


@responses.activate
def test_jellyfin_uses_the_items_route_with_user_id():
    responses.get(f"{URL}/Items", json={"Items": [episode(1, series="s9")], "TotalRecordCount": 1})
    responses.get(f"{URL}/Items", json={"Items": [{"Id": "s9", "ProviderIds": {"tvdb": "55"}}]})
    items = JellyfinClient(URL, "key").watched("u1")
    assert items[0].series_tvdb == 55
    assert "userId=u1" in responses.calls[0].request.url


@responses.activate
def test_items_without_numbers_or_tvdb_and_specials():
    responses.get(
        f"{URL}/Users/u1/Items",
        json={
            "Items": [
                episode(1, season=0),
                {**episode(2), "IndexNumber": None},
                episode(3, series="s2"),
            ],
            "TotalRecordCount": 3,
        },
    )
    responses.get(
        f"{URL}/Users/u1/Items",
        json={
            "Items": [{"Id": "s1", "ProviderIds": {"Tvdb": "1"}}, {"Id": "s2", "ProviderIds": {}}]
        },
    )
    items = EmbyClient(URL, "key").watched("u1")
    assert [(i.series_tvdb, i.season, i.episode) for i in items] == [(1, 0, 1), (None, 1, 3)]


@responses.activate
@pytest.mark.parametrize(
    "kwargs", [{"status": 401}, {"status": 500}, {"body": "x"}, {"body": requests.Timeout()}]
)
def test_errors_never_leak_the_key(kwargs):
    responses.get(f"{URL}/System/Info", **kwargs)
    with pytest.raises(MediaError) as info:
        EmbyClient(URL, "secret-key").test()
    assert "secret-key" not in str(info.value)


def test_client_for_picks_the_kind():
    assert isinstance(client_for("emby", URL, "k"), EmbyClient)
    assert isinstance(client_for("jellyfin", URL, "k"), JellyfinClient)
    with pytest.raises(ValueError):
        client_for("kodi", URL, "k")
