"""Notification channels and event resend (PLAN.md sections 7, 16.3)."""

from __future__ import annotations

import json
from typing import Any, Literal

from flask import Blueprint, current_app
from flask.typing import ResponseReturnValue
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from finalarr.api.common import ApiProblem, database, not_found, parse_body, secrets
from finalarr.db.models import Channel, Event
from finalarr.notify.messages import channel_test_text
from finalarr.notify.presets import PresetError, build_url, describe
from finalarr.notify.sender import SendError
from finalarr.services.delivery import DeliveryWorker, resend

bp = Blueprint("channels", __name__, url_prefix="/api/v1")

Kind = Literal["telegram", "discord", "pushover", "webhook", "apprise"]
Language = Literal["de", "en"]
EventName = Literal[
    "season_announced",
    "episodes_available",
    "finale_available",
    "part_complete",
    "season_complete",
    "sequel_announced",
    "news_mention",
    "episode_delayed",
]


class QuietIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


class ChannelTest(BaseModel):
    """The add-channel form; testing it before saving sends the same body."""

    model_config = ConfigDict(extra="forbid")

    kind: Kind
    fields: dict[str, str]
    language: Language = "de"
    name: str | None = None
    event_filter: list[EventName] = []
    enabled: bool = True
    quiet_hours: QuietIn | None = None


class ChannelIn(ChannelTest):
    name: str = Field(min_length=1, max_length=100)


class ChannelPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    kind: Kind | None = None
    fields: dict[str, str] | None = None
    language: Language | None = None
    event_filter: list[EventName] | None = None
    enabled: bool | None = None
    quiet_hours: QuietIn | None = None


class ResendIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel_id: int | None = None


def serialize(channel: Channel) -> dict[str, Any]:
    return {
        "id": channel.id,
        "name": channel.name,
        "kind": channel.kind,
        "target": describe(secrets().decrypt(channel.apprise_url_enc)),
        "enabled": channel.enabled,
        "language": channel.language,
        "event_filter": json.loads(channel.event_filter_json or "[]"),
        "quiet_hours": json.loads(channel.quiet_hours_json) if channel.quiet_hours_json else None,
    }


def _url(kind: str, fields: dict[str, str]) -> str:
    try:
        return build_url(kind, fields)
    except PresetError as error:
        raise ApiProblem(
            400, "validation", "Invalid channel", {f"fields.{error.field}": str(error)}
        ) from None


def _quiet_json(quiet: QuietIn | None) -> str | None:
    return quiet.model_dump_json() if quiet else None


def _load(s: Session, channel_id: int) -> Channel:
    channel = s.get(Channel, channel_id)
    if channel is None:
        raise not_found("Channel")
    return channel


def _send_test(url: str, language: str) -> ResponseReturnValue:
    worker: DeliveryWorker = current_app.extensions["finalarr.delivery"]
    try:
        worker.sender.send(url, channel_test_text(language))
    except SendError as error:
        raise ApiProblem(502, "channel_failed", str(error)) from None
    return {"ok": True}


@bp.get("/channels")
def list_channels() -> ResponseReturnValue:
    with database().session() as s:
        return [serialize(c) for c in s.scalars(select(Channel).order_by(Channel.name))]


@bp.post("/channels")
def create_channel() -> ResponseReturnValue:
    body = parse_body(ChannelIn)
    url = _url(body.kind, body.fields)
    with database().session() as s:
        channel = Channel(
            name=body.name.strip(),
            kind=body.kind,
            apprise_url_enc=secrets().encrypt(url),
            language=body.language,
            event_filter_json=json.dumps(body.event_filter),
            enabled=body.enabled,
            quiet_hours_json=_quiet_json(body.quiet_hours),
        )
        s.add(channel)
        s.commit()
        return serialize(channel), 201


@bp.post("/channels/test")
def test_unsaved() -> ResponseReturnValue:
    body = parse_body(ChannelTest)
    return _send_test(_url(body.kind, body.fields), body.language)


@bp.patch("/channels/<int:channel_id>")
def patch_channel(channel_id: int) -> ResponseReturnValue:
    body = parse_body(ChannelPatch)
    with database().session() as s:
        channel = _load(s, channel_id)
        if body.fields is not None:
            channel.kind = body.kind or channel.kind
            channel.apprise_url_enc = secrets().encrypt(_url(channel.kind, body.fields))
        if body.name is not None:
            channel.name = body.name.strip()
        if body.language is not None:
            channel.language = body.language
        if body.event_filter is not None:
            channel.event_filter_json = json.dumps(body.event_filter)
        if body.enabled is not None:
            channel.enabled = body.enabled
        if "quiet_hours" in body.model_fields_set:
            channel.quiet_hours_json = _quiet_json(body.quiet_hours)
        s.commit()
        return serialize(channel)


@bp.delete("/channels/<int:channel_id>")
def delete_channel(channel_id: int) -> ResponseReturnValue:
    with database().session() as s:
        s.delete(_load(s, channel_id))
        s.commit()
    return "", 204


@bp.post("/channels/<int:channel_id>/test")
def test_channel(channel_id: int) -> ResponseReturnValue:
    with database().session() as s:
        channel = _load(s, channel_id)
        url, language = secrets().decrypt(channel.apprise_url_enc), channel.language
    return _send_test(url, language)


@bp.post("/events/<int:event_id>/resend")
def resend_event(event_id: int) -> ResponseReturnValue:
    body = parse_body(ResendIn)
    with database().session() as s:
        if s.get(Event, event_id) is None:
            raise not_found("Event")
        count = resend(s, event_id, body.channel_id)
        s.commit()
    return {"queued": count}, 202
