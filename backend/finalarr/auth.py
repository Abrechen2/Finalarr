"""API authentication: ``X-Api-Key`` header, or a session cookie set by logging in
with the same key (PLAN.md section 9).

Cookie sessions carry a digest of the API key, so rotating the key ends them.
Writes over a cookie session need the ``X-Requested-With: finalarr`` header,
which a cross-site form cannot send (CSRF guard).
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress

from flask import Blueprint, Flask, current_app, request, session
from flask.typing import ResponseReturnValue

from finalarr.config import Settings
from finalarr.errors import api_error
from finalarr.ratelimit import RateLimiter

API_PREFIX = "/api/"
PUBLIC_ENDPOINTS = frozenset({"auth.login", "auth.status"})
CSRF_HEADER = "X-Requested-With"
CSRF_VALUE = "finalarr"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
LOGIN_FAILURES_PER_MINUTE = 5
# Headers a reverse proxy adds; without FINALARR_TRUSTED_PROXIES they mean "the peer
# address is a proxy, not the visitor".
PROXY_HEADERS = ("X-Forwarded-For", "Forwarded", "X-Real-IP")

# Home networks only; ipaddress' own is_private also counts documentation ranges.
LOCAL_NETWORKS = tuple(
    ipaddress.ip_network(n)
    for n in (
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
    )
)

bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")


def init_auth(app: Flask, settings: Settings) -> None:
    api_key = settings.api_key.get_secret_value()
    secret = settings.secret_key.get_secret_value()
    app.secret_key = hashlib.sha256(f"session|{secret}".encode()).hexdigest()
    app.config.update(
        SESSION_COOKIE_NAME="finalarr_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=settings.cookie_secure,
    )
    app.extensions["finalarr.api_key"] = api_key
    app.extensions["finalarr.auth_mode"] = settings.auth
    app.extensions["finalarr.trusted_proxies"] = settings.trusted_proxies
    app.extensions["finalarr.login_limiter"] = RateLimiter(LOGIN_FAILURES_PER_MINUTE, 60)

    @app.before_request
    def _guard() -> ResponseReturnValue | None:
        if not request.path.startswith(API_PREFIX):
            return None
        if _has_valid_header(api_key):
            return None
        needs_csrf = request.method not in SAFE_METHODS
        if needs_csrf and request.headers.get(CSRF_HEADER) != CSRF_VALUE:
            return api_error(403, "csrf", "Missing X-Requested-With header")
        if request.endpoint in PUBLIC_ENDPOINTS or _has_valid_session(api_key):
            return None
        if _local_client_allowed():
            return None
        return api_error(401, "unauthorized", "API key required")

    app.register_blueprint(bp)


def _local_client_allowed() -> bool:
    """FINALARR_AUTH=local: no login for clients on private networks (like Sonarr's
    "disabled for local addresses"). Behind a reverse proxy this relies on
    FINALARR_TRUSTED_PROXIES; a forwarded request without it always needs the key,
    otherwise every visitor would look like the proxy's LAN address."""
    if current_app.extensions.get("finalarr.auth_mode") != "local":
        return False
    if not current_app.extensions.get("finalarr.trusted_proxies") and any(
        h in request.headers for h in PROXY_HEADERS
    ):
        return False
    try:
        peer = ipaddress.ip_address(request.remote_addr or "")
    except ValueError:
        return False
    if isinstance(peer, ipaddress.IPv6Address) and peer.ipv4_mapped:
        peer = peer.ipv4_mapped
    return any(peer in network for network in LOCAL_NETWORKS)


def _key_digest(api_key: str) -> str:
    return hashlib.sha256(f"apikey|{api_key}".encode()).hexdigest()


def _has_valid_header(api_key: str) -> bool:
    supplied = request.headers.get("X-Api-Key", "")
    return bool(supplied) and hmac.compare_digest(supplied.encode(), api_key.encode())


def _has_valid_session(api_key: str) -> bool:
    stored = session.get("key_digest", "")
    return bool(stored) and hmac.compare_digest(stored, _key_digest(api_key))


def _api_key() -> str:
    return str(current_app.extensions["finalarr.api_key"])


@bp.post("/login")
def login() -> ResponseReturnValue:
    # Reserve a slot atomically; a successful login gives it back, so only
    # failures count and the owner is never locked out by their own logins.
    limiter: RateLimiter = current_app.extensions["finalarr.login_limiter"]
    client = request.remote_addr or "unknown"
    if not limiter.hit(client):
        return api_error(429, "rate_limited", "Too many login attempts, try again later")
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not isinstance(body.get("api_key"), str):
        limiter.forgive(client)
        return api_error(400, "bad_request", "Expected JSON body with api_key")
    api_key = _api_key()
    if not hmac.compare_digest(body["api_key"].encode(), api_key.encode()):
        return api_error(401, "unauthorized", "Invalid API key")
    limiter.forgive(client)
    session.clear()
    session["key_digest"] = _key_digest(api_key)
    session.permanent = True
    return {"authenticated": True}


@bp.post("/logout")
def logout() -> ResponseReturnValue:
    session.clear()
    return {"authenticated": False}


@bp.get("/status")
def status() -> ResponseReturnValue:
    authenticated = (
        _has_valid_session(_api_key()) or _has_valid_header(_api_key()) or _local_client_allowed()
    )
    return {"authenticated": authenticated, "mode": current_app.extensions["finalarr.auth_mode"]}


@bp.get("/check")
def check() -> ResponseReturnValue:
    return {"ok": True}
