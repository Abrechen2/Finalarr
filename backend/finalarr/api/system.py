"""System status and log tail (PLAN.md section 7)."""

from __future__ import annotations

from collections import deque

from flask import Blueprint, current_app, request
from flask.typing import ResponseReturnValue
from sqlalchemy import select

from finalarr.api.common import ApiProblem, database
from finalarr.db.models import SonarrInstance
from finalarr.logging_setup import redact
from finalarr.scheduler import SchedulerService, describe_jobs
from finalarr.version import get_version

bp = Blueprint("system", __name__, url_prefix="/api/v1/system")
MAX_TAIL = 1000
DEFAULT_TAIL = 200


@bp.get("/status")
def status() -> ResponseReturnValue:
    scheduler: SchedulerService = current_app.extensions["finalarr.scheduler"]
    with database().session() as s:
        instances = [
            {
                "id": i.id,
                "name": i.name,
                "enabled": i.enabled,
                "last_sync_at": i.last_sync_at.isoformat() if i.last_sync_at else None,
                "last_error": i.last_error,
            }
            for i in s.scalars(select(SonarrInstance).order_by(SonarrInstance.name))
        ]
    return {
        "version": get_version(),
        "db": "ok" if database().ping() else "error",
        "scheduler": {"running": scheduler.running, "jobs": describe_jobs(scheduler)},
        "instances": instances,
    }


@bp.get("/logs")
def logs() -> ResponseReturnValue:
    raw = request.args.get("tail", str(DEFAULT_TAIL))
    if not raw.isdigit() or not 1 <= int(raw) <= MAX_TAIL:
        raise ApiProblem(400, "bad_request", f"tail must be 1..{MAX_TAIL}")
    path = current_app.extensions["finalarr.settings"].data / "finalarr.log"
    if not path.is_file():
        return {"lines": []}
    with path.open(encoding="utf-8", errors="replace") as handle:
        lines = deque(handle, maxlen=int(raw))
    # Written redacted already; redacting again covers lines from older versions.
    return {"lines": [redact(line.rstrip("\n")) for line in lines]}
