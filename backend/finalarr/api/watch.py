"""Watch tracker: stats and the list of started series with what is still unwatched."""

from __future__ import annotations

from datetime import UTC, datetime

from flask import Blueprint, request
from flask.typing import ResponseReturnValue
from sqlalchemy import select
from sqlalchemy.orm import Session

from finalarr.api.common import ApiProblem, database, not_found
from finalarr.db import models as m
from finalarr.services.watch_tracker import SORTS, STATES, WEEKS, tracker_series, tracker_stats

bp = Blueprint("watch", __name__, url_prefix="/api/v1/watch")

MAX_WEEKS = 52


def _choice(name: str, allowed: tuple[str, ...]) -> str:
    value = request.args.get(name, allowed[0])
    if value not in allowed:
        raise ApiProblem(400, "bad_request", f"{name} must be one of {', '.join(allowed)}")
    return value


def _user(s: Session) -> int | None:
    """The ``user`` argument: a selected user's id, or none for everyone."""
    raw = request.args.get("user")
    if not raw:
        return None
    user = s.get(m.MediaUser, int(raw)) if raw.isdigit() else None
    if user is None or not user.selected:
        raise not_found("User")
    return user.id


def _weeks() -> int:
    raw = request.args.get("weeks", str(WEEKS))
    if not raw.isdigit() or not 1 <= int(raw) <= MAX_WEEKS:
        raise ApiProblem(400, "bad_request", f"weeks must be 1 to {MAX_WEEKS}")
    return int(raw)


@bp.get("/stats")
def stats() -> ResponseReturnValue:
    weeks = _weeks()
    with database().session() as s:
        users = [
            {"id": uid, "name": name, "server": server}
            for uid, name, server in s.execute(
                select(m.MediaUser.id, m.MediaUser.name, m.MediaServer.name)
                .join(m.MediaServer)
                .where(m.MediaUser.selected.is_(True), m.MediaServer.enabled.is_(True))
                .order_by(m.MediaUser.name)
            )
        ]
        return tracker_stats(s, _user(s), datetime.now(UTC).date(), weeks) | {"users": users}


@bp.get("/series")
def series() -> ResponseReturnValue:
    state, sort = _choice("state", STATES), _choice("sort", SORTS)
    with database().session() as s:
        return tracker_series(s, _user(s), datetime.now(UTC).date(), state, sort)
