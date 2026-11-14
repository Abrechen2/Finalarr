"""AniList search and manual season pins."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, current_app, request
from flask.typing import ResponseReturnValue
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete

from finalarr.api.common import ApiProblem, database, not_found, parse_body
from finalarr.api.series import series_detail
from finalarr.db.models import AnilistMapping, Season
from finalarr.services.anilist_cache import CachedAnilist
from finalarr.services.enricher import AnimeEnricher
from finalarr.sources.anilist import AnilistError, AnilistMedia

bp = Blueprint("anilist", __name__, url_prefix="/api/v1")
MAX_PINS = 4


class PinIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anilist_ids: list[int] = Field(max_length=MAX_PINS)

    def model_post_init(self, _context: Any) -> None:
        if any(i < 1 for i in self.anilist_ids):
            raise ValueError("anilist ids must be positive")


def candidate(media: AnilistMedia) -> dict[str, Any]:
    return {
        "id": media.id,
        "title": media.title,
        "romaji": media.titles.romaji,
        "format": media.format,
        "status": media.status,
        "episodes": media.episodes,
        "start_date": media.start_date.isoformat() if media.start_date else None,
    }


@bp.get("/anilist/search")
def search() -> ResponseReturnValue:
    text = request.args.get("q", "").strip()
    if not text:
        raise ApiProblem(400, "bad_request", "q is required")
    anilist: CachedAnilist = current_app.extensions["finalarr.anilist"]
    try:
        return [candidate(m) for m in anilist.search(text)]
    except AnilistError as error:
        raise ApiProblem(503, "anilist_unavailable", str(error)) from None


@bp.put("/seasons/<int:season_id>/anilist")
def pin(season_id: int) -> ResponseReturnValue:
    body = parse_body(PinIn)
    with database().session() as s:
        season = s.get(Season, season_id)
        if season is None:
            raise not_found("Season")
        series = season.series
        if series.tvdb_id is None:
            raise ApiProblem(409, "no_tvdb_id", "Sonarr has no TVDB id for this series")
        s.execute(
            delete(AnilistMapping).where(
                AnilistMapping.tvdb_id == series.tvdb_id,
                AnilistMapping.tvdb_season == season.number,
                AnilistMapping.source == "manual",
            )
        )
        s.add_all(
            AnilistMapping(
                tvdb_id=series.tvdb_id, tvdb_season=season.number, anilist_id=i, source="manual"
            )
            for i in dict.fromkeys(body.anilist_ids)
        )
        s.commit()
        series_id = series.id
    enricher: AnimeEnricher = current_app.extensions["finalarr.enricher"]
    try:
        enricher.enrich(series_id)
    except AnilistError:
        return {"saved": True, "enriched": False}, 202
    with database().session() as s:
        detail = series_detail(s.get_one(Season, season_id).series)
    view: dict[str, Any] = next(x for x in detail["seasons"] if x["id"] == season_id)
    return view
