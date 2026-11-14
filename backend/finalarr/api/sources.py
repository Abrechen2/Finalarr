"""Data sources: what Finalarr asks, under which terms, and the user's on/off switches."""

from __future__ import annotations

from flask import Blueprint, current_app
from flask.typing import ResponseReturnValue
from pydantic import BaseModel, ConfigDict, StrictBool

from finalarr.api.common import database, not_found, parse_body
from finalarr.services.source_catalog import IDS, set_source, source_views

bp = Blueprint("sources", __name__, url_prefix="/api/v1")


class SourcePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: StrictBool


@bp.get("/sources")
def list_sources() -> ResponseReturnValue:
    with database().session() as s:
        return source_views(s, current_app.extensions["finalarr.settings"])


@bp.patch("/sources/<source_id>")
def patch_source(source_id: str) -> ResponseReturnValue:
    if source_id not in IDS:
        raise not_found("Source")
    body = parse_body(SourcePatch)
    with database().session() as s:
        set_source(s, source_id, body.enabled)
        s.commit()
        views = source_views(s, current_app.extensions["finalarr.settings"])
    return next(v for v in views if v["id"] == source_id)
