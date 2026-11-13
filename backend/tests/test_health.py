from finalarr.version import get_version


def test_health_is_unauthenticated_and_reports_version(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "version": get_version()}


def test_version_matches_version_file():
    from pathlib import Path

    expected = (Path(__file__).parents[1] / "VERSION").read_text().strip()
    assert get_version() == expected


def test_version_env_override_wins(monkeypatch):
    monkeypatch.setenv("FINALARR_VERSION", "0.1.0-rc.2")
    assert get_version() == "0.1.0-rc.2"


def test_version_falls_back_to_package_metadata(monkeypatch, tmp_path):
    from finalarr import version as version_module

    monkeypatch.delenv("FINALARR_VERSION", raising=False)
    monkeypatch.setattr(version_module, "_VERSION_FILE", tmp_path / "missing")
    monkeypatch.setattr(version_module, "version", lambda _name: "9.9.9")
    assert get_version() == "9.9.9"


def test_version_unknown_when_not_installed(monkeypatch, tmp_path):
    from finalarr import version as version_module

    def not_found(_name):
        raise version_module.PackageNotFoundError

    monkeypatch.delenv("FINALARR_VERSION", raising=False)
    monkeypatch.setattr(version_module, "_VERSION_FILE", tmp_path / "missing")
    monkeypatch.setattr(version_module, "version", not_found)
    assert get_version() == "0.0.0+unknown"
