"""Per-season overrides and global rules (PLAN.md sections 7, 4.2)."""

from __future__ import annotations

from typing import Literal

from flask import Blueprint, current_app
from flask.typing import ResponseReturnValue
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from finalarr.api.common import database, not_found, parse_body
from finalarr.api.series import series_detail
from finalarr.db.models import Season
from finalarr.services.reconcile_queue import enqueue
from finalarr.services.settings_store import load_settings, save_settings

bp = Blueprint("rules", __name__, url_prefix="/api/v1")
MAX_EPISODES = 2000


class SeasonPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_override: int | None = Field(default=None, ge=1, le=MAX_EPISODES)
    parts_mode: Literal["season", "parts"] | None = None


class SettingsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    renotify_on_growth: StrictBool | None = None
    renotify_after_file_loss: StrictBool | None = None
    include_specials_default: StrictBool | None = None
    respect_monitoring_default: StrictBool | None = None
    stable_runs: int | None = Field(default=None, ge=1, le=10)
    reconcile_interval_minutes: int | None = Field(default=None, ge=5, le=1440)


def _nudge() -> None:
    nudge = current_app.extensions.get("finalarr.nudge")
    if nudge:
        nudge()


@bp.patch("/seasons/<int:season_id>")
def patch_season(season_id: int) -> ResponseReturnValue:
    body = parse_body(SeasonPatch)
    with database().session() as s:
        season = s.get(Season, season_id)
        if season is None:
            raise not_found("Season")
        if "expected_override" in body.model_fields_set:
            season.expected_override = body.expected_override
        if body.parts_mode is not None:
            season.parts_mode = body.parts_mode
        enqueue(s, season.series.instance_id, season.series.sonarr_id)
        s.commit()
        detail = series_detail(season.series)
    _nudge()
    season_view: dict[str, object] = next(x for x in detail["seasons"] if x["id"] == season_id)
    return season_view


@bp.get("/settings")
def get_settings() -> ResponseReturnValue:
    with database().session() as s:
        return load_settings(s)


@bp.patch("/settings")
def patch_settings() -> ResponseReturnValue:
    body = parse_body(SettingsPatch)
    with database().session() as s:
        save_settings(s, body.model_dump(exclude_none=True))
        s.commit()
        return load_settings(s)
