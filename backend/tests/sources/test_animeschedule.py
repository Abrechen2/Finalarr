import pytest
import requests
import responses

from finalarr.sources.animeschedule import (
    ANIMESCHEDULE_URL,
    AnimeScheduleClient,
    AnimeScheduleError,
)

FRIEREN = {
    "page": 1,
    "anime": [
        {
            "route": "sousou-no-frieren",
            "premier": "2023-09-29T00:00:00Z",
            "subPremier": "0001-01-01T00:00:00Z",
            "dubPremier": "2023-10-13T00:00:00Z",
            "dubTime": "2026-11-20T18:30:00Z",
            "delayedUntil": "2026-11-27T00:00:00Z",
            "delayedDesc": "Production delay",
            "dubExists": True,
        }
    ],
}


@responses.activate
def test_dub_info_by_mal_id_with_bearer_token():
    responses.get(f"{ANIMESCHEDULE_URL}/anime", json=FRIEREN)
    dub = AnimeScheduleClient("tok").by_mal_id(52991)
    request = responses.calls[0].request
    assert "mal-ids=52991" in request.url
    assert request.headers["Authorization"] == "Bearer tok"
    assert dub is not None
    assert dub.url == "https://animeschedule.net/anime/sousou-no-frieren"
    assert dub.dub_premiere.isoformat() == "2023-10-13T00:00:00+00:00"
    assert dub.dub_next.isoformat() == "2026-11-20T18:30:00+00:00"
    assert dub.delayed_until.isoformat() == "2026-11-27T00:00:00+00:00"
    assert dub.delay_note == "Production delay"


@responses.activate
def test_zero_dates_and_unknown_anime():
    responses.get(
        f"{ANIMESCHEDULE_URL}/anime",
        json={"anime": [{"route": "x", "dubPremier": "0001-01-01T00:00:00Z"}]},
    )
    responses.get(f"{ANIMESCHEDULE_URL}/anime", json={"anime": []})
    client = AnimeScheduleClient("tok")
    dub = client.by_mal_id(1)
    assert dub is not None and dub.dub_premiere is None and dub.dub_next is None
    assert client.by_mal_id(2) is None


@responses.activate
@pytest.mark.parametrize(
    "kwargs", [{"status": 401}, {"status": 500}, {"body": "x"}, {"body": requests.Timeout()}]
)
def test_errors_never_leak_the_token(kwargs):
    responses.get(f"{ANIMESCHEDULE_URL}/anime", **kwargs)
    with pytest.raises(AnimeScheduleError) as info:
        AnimeScheduleClient("secret-token").by_mal_id(1)
    assert "secret-token" not in str(info.value)
