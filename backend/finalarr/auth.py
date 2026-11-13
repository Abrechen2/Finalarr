"""API authentication: ``X-Api-Key`` header, or a session cookie set by logging in
with the same key (PLAN.md section 9).

Cookie sessions carry a digest of the API key, so rotating the key ends them.
Writes over a cookie session need the ``X-Requested-With: finalarr`` header,
which a cross-site form cannot send (CSRF guard).
"""

from __future__ import annotations

import hashlib
import hmac

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
        return api_error(401, "unauthorized", "API key required")

    app.register_blueprint(bp)


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
    # Only failures count, so the owner is never locked out by their own logins.
    limiter: RateLimiter = current_app.extensions["finalarr.login_limiter"]
    client = request.remote_addr or "unknown"
    if limiter.blocked(client):
        return api_error(429, "rate_limited", "Too many login attempts, try again later")
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not isinstance(body.get("api_key"), str):
        return api_error(400, "bad_request", "Expected JSON body with api_key")
    api_key = _api_key()
    if not hmac.compare_digest(body["api_key"].encode(), api_key.encode()):
        limiter.hit(client)
        return api_error(401, "unauthorized", "Invalid API key")
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
    return {"authenticated": _has_valid_session(_api_key()) or _has_valid_header(_api_key())}


@bp.get("/check")
def check() -> ResponseReturnValue:
    return {"ok": True}
