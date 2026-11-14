"""SQLAlchemy models; schema per PLAN.md section 6 incl. the constraints from 20.1."""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

SEASON_STATES = ("unknown", "scheduled", "airing", "aired", "complete")
EVENT_TYPES = (
    "season_announced",
    "episodes_available",
    "finale_available",
    "season_complete",
    "part_complete",
    "sequel_announced",
    "news_mention",
    "episode_delayed",
)
SERIES_TYPES = ("standard", "anime", "daily")
CHANNEL_KINDS = ("telegram", "discord", "pushover", "webhook", "apprise")
DELIVERY_STATES = ("pending", "sent", "failed")


def utcnow() -> datetime:
    return datetime.now(UTC)


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class Base(DeclarativeBase):
    pass


class SonarrInstance(Base):
    __tablename__ = "sonarr_instances"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    url: Mapped[str] = mapped_column(String(500))
    api_key_enc: Mapped[str] = mapped_column(Text)
    webhook_token: Mapped[str] = mapped_column(String(64), unique=True)
    basic_user: Mapped[str | None] = mapped_column(String(100))
    basic_pass_enc: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    series: Mapped[list[Series]] = relationship(
        back_populates="instance", cascade="all, delete-orphan"
    )


class Series(Base):
    __tablename__ = "series"
    __table_args__ = (
        UniqueConstraint("instance_id", "sonarr_id"),
        CheckConstraint(_in("series_type", SERIES_TYPES), name="ck_series_type"),
        CheckConstraint(
            _in("anilist_resolution", ("auto", "manual", "unresolved", "none")),
            name="ck_series_anilist",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    instance_id: Mapped[int] = mapped_column(ForeignKey("sonarr_instances.id", ondelete="CASCADE"))
    sonarr_id: Mapped[int] = mapped_column(Integer)
    tvdb_id: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(500))
    sort_title: Mapped[str] = mapped_column(String(500), default="")
    title_slug: Mapped[str] = mapped_column(String(500), default="")
    year: Mapped[int | None] = mapped_column(Integer)
    series_type: Mapped[str] = mapped_column(String(20), default="standard")
    status: Mapped[str] = mapped_column(String(20), default="")
    poster_url: Mapped[str | None] = mapped_column(String(1000))
    fanart_url: Mapped[str | None] = mapped_column(String(1000))
    overview: Mapped[str] = mapped_column(Text, default="", server_default="")
    network: Mapped[str] = mapped_column(String(200), default="", server_default="")
    runtime: Mapped[int | None] = mapped_column(Integer)
    genres_json: Mapped[str] = mapped_column(Text, default="[]", server_default="[]")
    # Sonarr tag labels, JSON list; used for "follow all with tag".
    tags_json: Mapped[str] = mapped_column(Text, default="[]", server_default="[]")
    monitored: Mapped[bool] = mapped_column(Boolean, default=True)
    followed: Mapped[bool] = mapped_column(Boolean, default=False)
    include_specials: Mapped[bool] = mapped_column(Boolean, default=False)
    respect_monitoring: Mapped[bool] = mapped_column(Boolean, default=True)
    # Shown in the calendar and the iCal feed (when followed).
    calendar: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    anilist_id: Mapped[int | None] = mapped_column(Integer)
    anilist_resolution: Mapped[str] = mapped_column(String(20), default="none")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    instance: Mapped[SonarrInstance] = relationship(back_populates="series")
    seasons: Mapped[list[Season]] = relationship(
        back_populates="series", cascade="all, delete-orphan", order_by="Season.number"
    )


class Season(Base):
    __tablename__ = "seasons"
    __table_args__ = (
        UniqueConstraint("series_id", "number"),
        CheckConstraint(_in("state", SEASON_STATES), name="ck_seasons_state"),
        CheckConstraint(_in("parts_mode", ("season", "parts")), name="ck_seasons_parts_mode"),
        CheckConstraint("number >= 0", name="ck_seasons_number"),
        CheckConstraint(
            "expected_override IS NULL OR expected_override > 0", name="ck_seasons_override"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    series_id: Mapped[int] = mapped_column(ForeignKey("series.id", ondelete="CASCADE"))
    number: Mapped[int] = mapped_column(Integer)
    monitored: Mapped[bool] = mapped_column(Boolean, default=True)
    expected_count: Mapped[int | None] = mapped_column(Integer)
    expected_source: Mapped[str | None] = mapped_column(String(20))
    expected_override: Mapped[int | None] = mapped_column(Integer)
    anilist_count: Mapped[int | None] = mapped_column(Integer)
    anilist_start: Mapped[date | None] = mapped_column(Date)
    disputed: Mapped[bool] = mapped_column(Boolean, default=False)
    parts_mode: Mapped[str] = mapped_column(String(10), default="season")
    state: Mapped[str] = mapped_column(String(20), default="unknown")
    state_since: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Serialised core.model.SeasonMemory; the evaluator's only persistent state.
    memory_json: Mapped[str | None] = mapped_column(Text)
    last_evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    series: Mapped[Series] = relationship(back_populates="seasons")
    episodes: Mapped[list[Episode]] = relationship(
        back_populates="season", cascade="all, delete-orphan", order_by="Episode.number"
    )
    parts: Mapped[list[AnimePart]] = relationship(
        back_populates="season", cascade="all, delete-orphan", order_by="AnimePart.part_index"
    )


class Episode(Base):
    __tablename__ = "episodes"
    __table_args__ = (
        UniqueConstraint("season_id", "number"),
        UniqueConstraint("season_id", "sonarr_episode_id"),
        CheckConstraint("number >= 0", name="ck_episodes_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id", ondelete="CASCADE"))
    sonarr_episode_id: Mapped[int] = mapped_column(Integer)
    number: Mapped[int] = mapped_column(Integer)
    absolute_number: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(500), default="")
    air_date_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    monitored: Mapped[bool] = mapped_column(Boolean, default=True)
    has_file: Mapped[bool] = mapped_column(Boolean, default=False)
    finale_type: Mapped[str | None] = mapped_column(String(20))
    # Air date before the last postponement; cleared when the episode airs.
    delayed_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    season: Mapped[Season] = relationship(back_populates="episodes")


class AnimePart(Base):
    __tablename__ = "anime_parts"
    __table_args__ = (
        UniqueConstraint("season_id", "part_index"),
        CheckConstraint("episode_from <= episode_to", name="ck_anime_parts_range"),
        CheckConstraint("part_index >= 1", name="ck_anime_parts_index"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id", ondelete="CASCADE"))
    anilist_id: Mapped[int] = mapped_column(Integer)
    part_index: Mapped[int] = mapped_column(Integer)
    episode_from: Mapped[int] = mapped_column(Integer)
    episode_to: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(30), default="")
    notified: Mapped[bool] = mapped_column(Boolean, default=False)

    season: Mapped[Season] = relationship(back_populates="parts")


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint(_in("type", EVENT_TYPES), name="ck_events_type"),
        Index("ix_events_series_id", "series_id"),
        Index("ix_events_season_id", "season_id"),
        Index("ix_events_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(30))
    instance_id: Mapped[int | None] = mapped_column(
        ForeignKey("sonarr_instances.id", ondelete="SET NULL")
    )
    series_id: Mapped[int | None] = mapped_column(ForeignKey("series.id", ondelete="SET NULL"))
    season_id: Mapped[int | None] = mapped_column(ForeignKey("seasons.id", ondelete="SET NULL"))
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    deliveries: Mapped[list[Delivery]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )


class Channel(Base):
    __tablename__ = "channels"
    __table_args__ = (CheckConstraint(_in("kind", CHANNEL_KINDS), name="ck_channels_kind"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(20))
    apprise_url_enc: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    language: Mapped[str] = mapped_column(String(5), default="de")
    event_filter_json: Mapped[str] = mapped_column(Text, default="[]")
    quiet_hours_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    deliveries: Mapped[list[Delivery]] = relationship(
        back_populates="channel", cascade="all, delete-orphan"
    )


class Delivery(Base):
    __tablename__ = "deliveries"
    __table_args__ = (
        UniqueConstraint("event_id", "channel_id"),
        CheckConstraint(_in("status", DELIVERY_STATES), name="ck_deliveries_status"),
        CheckConstraint("attempts >= 0", name="ck_deliveries_attempts"),
        Index("ix_deliveries_channel_id", "channel_id"),
        Index(
            "ix_deliveries_due",
            "next_attempt_at",
            sqlite_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(10), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    event: Mapped[Event] = relationship(back_populates="deliveries")
    channel: Mapped[Channel] = relationship(back_populates="deliveries")


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value_json: Mapped[str] = mapped_column(Text)


class ReconcileRequest(Base):
    """Durable, per-series coalesced reconcile trigger (PLAN.md 4.5). series 0 = full sync."""

    __tablename__ = "reconcile_requests"
    __table_args__ = (UniqueConstraint("instance_id", "sonarr_series_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    instance_id: Mapped[int] = mapped_column(ForeignKey("sonarr_instances.id", ondelete="CASCADE"))
    sonarr_series_id: Mapped[int] = mapped_column(Integer, default=0)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AnilistMapping(Base):
    __tablename__ = "anilist_mappings"
    __table_args__ = (
        CheckConstraint(_in("source", ("fribb", "manual")), name="ck_anilist_mappings_source"),
    )

    tvdb_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tvdb_season: Mapped[int] = mapped_column(Integer, primary_key=True)
    anilist_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(10), primary_key=True, default="fribb")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FribbId(Base):
    """AniList ↔ MyAnimeList id pairs from Fribb's list (also for entries without TVDB)."""

    __tablename__ = "fribb_ids"

    anilist_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mal_id: Mapped[int] = mapped_column(Integer, index=True)


class AnilistCache(Base):
    __tablename__ = "anilist_cache"

    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    body_json: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
