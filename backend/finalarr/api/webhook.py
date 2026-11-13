"""Sonarr webhook receiver. The body is only a trigger (PLAN.md section 9).

Order matters: size cap, IP allowlist, token, Basic auth and rate limit are all
checked before the body is parsed. Nothing from the body is stored except the
series id used to schedule a reconcile.
"""

from __future__ import annotations

import base64
import binascii
import hmac
import ipaddress
import json
from typing import Any

from flask import Blueprint, current_app, request
from flask.typing import ResponseReturnValue
from sqlalchemy import select

from finalarr.api.common import database, secrets
from finalarr.db.models import SonarrInstance
from finalarr.errors import api_error
from finalarr.ratelimit import RateLimiter
from finalarr.services.reconcile_queue import FULL_SYNC, enqueue

bp = Blueprint("webhook", __name__, url_prefix="/webhook")
MAX_BODY_BYTES = 64 * 1024
TRIGGERS_PER_MINUTE = 60

Network = ipaddress.IPv4Network | ipaddress.IPv6Network


def parse_allowlist(raw: str) -> list[Network]:
    return [
        ipaddress.ip_network(part.strip(), strict=False) for part in raw.split(",") if part.strip()
    ]


def _peer_allowed(allow: list[Network]) -> bool:
    if not allow:
        return True
    try:
        peer = ipaddress.ip_address(request.remote_addr or "")
    except ValueError:
        return False
    return any(peer in network for network in allow)


def _basic_auth_ok(instance: SonarrInstance) -> bool:
    if not instance.basic_user or not instance.basic_pass_enc:
        return True
    scheme, _, encoded = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "basic":
        return False
    try:
        user, _, password = base64.b64decode(encoded).decode().partition(":")
    except (binascii.Error, UnicodeDecodeError):
        return False
    expected = secrets().decrypt(instance.basic_pass_enc)
    return hmac.compare_digest(user, instance.basic_user) & hmac.compare_digest(
        password.encode(), expected.encode()
    )


def _json_or_none(raw: bytes) -> Any:
    try:
        return json.loads(raw)
    except ValueError:
        return None


def _series_id(body: Any) -> int:
    series = body.get("series") if isinstance(body, dict) else None
    sid = series.get("id") if isinstance(series, dict) else None
    return sid if isinstance(sid, int) and not isinstance(sid, bool) and sid > 0 else FULL_SYNC


@bp.post("/sonarr/<token>")
def sonarr(token: str) -> ResponseReturnValue:
    # Reads stop one byte past the cap, so a chunked body without Content-Length
    # can never be buffered in full; the length check below then rejects it.
    request.max_content_length = MAX_BODY_BYTES + 1
    if (request.content_length or 0) > MAX_BODY_BYTES:
        return api_error(413, "too_large", "Body too large")
    if not _peer_allowed(current_app.extensions["finalarr.webhook_allow"]):
        return api_error(403, "forbidden", "Source address not allowed")
    with database().session() as s:
        instance = s.scalar(
            select(SonarrInstance).where(
                SonarrInstance.webhook_token == token, SonarrInstance.enabled.is_(True)
            )
        )
        if instance is None:
            return api_error(404, "not_found", "Not found")
        if not _basic_auth_ok(instance):
            return api_error(401, "unauthorized", "Basic auth required")
        limiter: RateLimiter = current_app.extensions["finalarr.webhook_limiter"]
        if not limiter.hit(token):
            return api_error(429, "rate_limited", "Too many webhook calls")
        raw = request.get_data(cache=False)
        if len(raw) > MAX_BODY_BYTES:
            return api_error(413, "too_large", "Body too large")
        body = _json_or_none(raw)
        if isinstance(body, dict) and body.get("eventType") == "Test":
            return {"ok": True}
        enqueue(s, instance.id, _series_id(body))
        s.commit()
    nudge = current_app.extensions.get("finalarr.nudge")
    if nudge:
        nudge()
    return {"queued": True}, 202
