def test_sources_list_and_switch(api):
    sources = api.get("/api/v1/sources").get_json()
    by_id = {s["id"]: s for s in sources}
    assert by_id["tvmaze"]["enabled"] is True
    assert by_id["tmdb"]["needs_key"] is True
    body = api.patch("/api/v1/sources/tvmaze", json={"enabled": False}).get_json()
    assert body["enabled"] is False
    assert {s["id"]: s for s in api.get("/api/v1/sources").get_json()}["tvmaze"]["enabled"] is False


def test_unknown_source_and_bad_body(api):
    assert api.patch("/api/v1/sources/nope", json={"enabled": False}).status_code == 404
    assert api.patch("/api/v1/sources/tvmaze", json={"enabled": "no"}).status_code == 400
    assert api.patch("/api/v1/sources/tvmaze", json={}).status_code == 400
