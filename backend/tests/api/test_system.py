import logging


def test_status_reports_version_db_scheduler_and_instances(api, instance):
    body = api.get("/api/v1/system/status").get_json()
    assert body["db"] == "ok"
    assert body["scheduler"] == {"running": False, "jobs": []}
    assert body["instances"][0]["name"] == "Home"
    assert "version" in body


def test_logs_tail_is_redacted(api, settings):
    logging.getLogger("finalarr.test").warning("call with apikey=topsecret")
    for handler in logging.getLogger().handlers:
        handler.flush()
    lines = api.get("/api/v1/system/logs?tail=5").get_json()["lines"]
    assert any("call with" in line for line in lines)
    assert not any("topsecret" in line for line in lines)


def test_logs_tail_bounds(api):
    assert api.get("/api/v1/system/logs?tail=0").status_code == 400
    assert api.get("/api/v1/system/logs?tail=5000").status_code == 400
