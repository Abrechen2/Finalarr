from .conftest import API_KEY

CSRF = {"X-Requested-With": "finalarr"}


def test_api_without_credentials_is_401(client):
    response = client.get("/api/v1/auth/check")
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "unauthorized"


def test_api_with_wrong_key_is_401(client):
    assert client.get("/api/v1/auth/check", headers={"X-Api-Key": "wrong"}).status_code == 401


def test_api_with_header_key_is_allowed(client):
    response = client.get("/api/v1/auth/check", headers={"X-Api-Key": API_KEY})
    assert response.status_code == 200


def test_health_stays_unauthenticated(client):
    assert client.get("/health").status_code == 200


def test_status_reports_session_state(client):
    assert client.get("/api/v1/auth/status").get_json() == {"authenticated": False}


def test_login_with_wrong_key_is_401(client):
    response = client.post("/api/v1/auth/login", json={"api_key": "nope"}, headers=CSRF)
    assert response.status_code == 401


def test_login_without_body_is_400(client):
    response = client.post("/api/v1/auth/login", data="x", headers=CSRF)
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "bad_request"


def test_login_sets_httponly_cookie_and_authenticates(client):
    response = client.post("/api/v1/auth/login", json={"api_key": API_KEY}, headers=CSRF)
    assert response.status_code == 200
    cookie = response.headers["Set-Cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie
    assert client.get("/api/v1/auth/check").status_code == 200
    assert client.get("/api/v1/auth/status").get_json() == {"authenticated": True}


def test_cookie_session_needs_csrf_header_for_writes(client):
    client.post("/api/v1/auth/login", json={"api_key": API_KEY}, headers=CSRF)
    assert client.post("/api/v1/auth/logout").status_code == 403
    assert client.post("/api/v1/auth/logout", headers=CSRF).status_code == 200
    assert client.get("/api/v1/auth/check").status_code == 401


def test_login_itself_needs_csrf_header(client):
    assert client.post("/api/v1/auth/login", json={"api_key": API_KEY}).status_code == 403


def test_session_dies_when_the_api_key_changes(settings, tmp_path):
    from finalarr.app import create_app

    first = create_app(settings=settings, static_dir=tmp_path)
    client = first.test_client()
    client.post("/api/v1/auth/login", json={"api_key": API_KEY}, headers=CSRF)
    rotated = settings.model_copy(update={"api_key": type(settings.api_key)("x" * 32)})
    second = create_app(settings=rotated, static_dir=tmp_path).test_client()
    second._cookies = client._cookies
    assert second.get("/api/v1/auth/check").status_code == 401


def test_login_is_rate_limited(client):
    for _ in range(5):
        client.post("/api/v1/auth/login", json={"api_key": "nope"}, headers=CSRF)
    response = client.post("/api/v1/auth/login", json={"api_key": API_KEY}, headers=CSRF)
    assert response.status_code == 429
    assert response.get_json()["error"]["code"] == "rate_limited"


def test_successful_logins_do_not_use_up_the_limit(client):
    for _ in range(8):
        response = client.post("/api/v1/auth/login", json={"api_key": API_KEY}, headers=CSRF)
        assert response.status_code == 200


def test_limit_follows_the_real_client_behind_a_trusted_proxy(settings, tmp_path):
    from finalarr.app import create_app

    proxied = settings.model_copy(update={"trusted_proxies": 1})
    client = create_app(settings=proxied, static_dir=tmp_path).test_client()
    for _ in range(5):
        client.post(
            "/api/v1/auth/login",
            json={"api_key": "nope"},
            headers={**CSRF, "X-Forwarded-For": "10.0.0.66"},
        )
    other = client.post(
        "/api/v1/auth/login",
        json={"api_key": API_KEY},
        headers={**CSRF, "X-Forwarded-For": "10.0.0.7"},
    )
    assert other.status_code == 200


def test_forwarded_header_is_ignored_without_trusted_proxies(client):
    for i in range(5):
        client.post(
            "/api/v1/auth/login",
            json={"api_key": "nope"},
            headers={**CSRF, "X-Forwarded-For": f"10.0.0.{i}"},
        )
    response = client.post("/api/v1/auth/login", json={"api_key": API_KEY}, headers=CSRF)
    assert response.status_code == 429
